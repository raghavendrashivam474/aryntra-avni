"""V2.0 Real-World Voice Identity Evaluation Harness.

Provides reproducible experiment infrastructure for evaluating
Avni's voice identity pipeline with real authorized human speech.

This module lives at the experiment boundary and does NOT modify
any core Avni contracts, capabilities, or adapters.
"""

import hashlib
import io
import json
import logging
import struct
import time
import wave
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audio Utilities (experiment-level preprocessing)
# ---------------------------------------------------------------------------

def resample_wav_to_16k(audio_bytes: bytes) -> bytes:
    """Resample WAV audio to 16kHz mono 16-bit PCM.

    This handles the gap identified in S0 Finding 1: the core preprocessor
    does not resample. We handle it here at the experiment boundary.

    Uses linear interpolation for simplicity. For production use, a
    proper resampler (e.g., librosa, scipy.signal.resample) would be
    preferred, but we avoid adding dependencies at the experiment layer.
    """
    buf = io.BytesIO(audio_bytes)
    with wave.open(buf, "rb") as wf:
        src_rate = wf.getframerate()
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    target_rate = 16000

    # Parse samples
    if width == 2:
        n_samples = len(raw) // 2
        samples = list(struct.unpack(f"<{n_samples}h", raw))
    else:
        raise ValueError(f"Unsupported sample width: {width}")

    # Stereo to mono
    if channels == 2:
        mono = []
        for i in range(0, len(samples), 2):
            left = samples[i]
            right = samples[i + 1] if i + 1 < len(samples) else left
            mono.append((left + right) // 2)
        samples = mono

    # Resample if needed
    if src_rate != target_rate:
        ratio = target_rate / src_rate
        new_length = int(len(samples) * ratio)
        resampled = []
        for i in range(new_length):
            src_pos = i / ratio
            src_idx = int(src_pos)
            frac = src_pos - src_idx
            if src_idx + 1 < len(samples):
                val = samples[src_idx] * (1 - frac) + samples[src_idx + 1] * frac
            else:
                val = samples[min(src_idx, len(samples) - 1)]
            resampled.append(int(max(-32768, min(32767, val))))
        samples = resampled

    # Serialize back to WAV
    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(target_rate)
        wf.writeframes(struct.pack(f"<{len(samples)}h", *samples))

    return out_buf.getvalue()


def get_wav_info(audio_bytes: bytes) -> Dict[str, Any]:
    """Extract metadata from WAV bytes."""
    buf = io.BytesIO(audio_bytes)
    try:
        with wave.open(buf, "rb") as wf:
            return {
                "sample_rate": wf.getframerate(),
                "channels": wf.getnchannels(),
                "sample_width": wf.getsampwidth(),
                "n_frames": wf.getnframes(),
                "duration_seconds": round(wf.getnframes() / wf.getframerate(), 3)
                    if wf.getframerate() > 0 else 0,
            }
    except Exception as e:
        return {"error": str(e)}


def hash_audio(audio_bytes: bytes) -> str:
    """SHA-256 hash of audio bytes for provenance tracking."""
    return hashlib.sha256(audio_bytes).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Experiment Data Structures
# ---------------------------------------------------------------------------

@dataclass
class ExperimentConfig:
    """Configuration for a V2.0 evaluation run."""
    experiment_id: str
    data_dir: str
    output_dir: str
    speakers: List[str] = field(default_factory=lambda: ["speaker_a", "speaker_b"])
    enrollment_count: int = 2
    evaluation_count: int = 3
    test_texts: List[str] = field(default_factory=lambda: [
        "The quick brown fox jumps over the lazy dog.",
        "Hello, my name is Avni and I am testing voice identity.",
        "Today is a beautiful day for scientific research.",
        "The temperature outside is seventy two degrees.",
        "Can you hear the difference between these two voices?",
    ])
    git_commit: str = ""
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class SampleRecord:
    """Metadata for a single audio sample in the experiment."""
    sample_id: str
    speaker_id: str
    role: str  # "enrollment" or "evaluation" or "generated"
    file_path: str
    audio_hash: str
    duration_seconds: float
    sample_rate: int
    channels: int


@dataclass
class MetricRecord:
    """A single metric measurement."""
    metric_name: str
    speaker_a_id: str
    speaker_b_id: str
    value: float
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExperimentResult:
    """Complete results from a V2.0 evaluation run."""
    experiment_id: str
    timestamp: str
    config: Dict[str, Any]
    samples: List[Dict[str, Any]] = field(default_factory=list)
    metrics: List[Dict[str, Any]] = field(default_factory=list)
    generated_files: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info("Experiment results saved to %s", path)


# ---------------------------------------------------------------------------
# Core Evaluation Harness
# ---------------------------------------------------------------------------

class V2EvaluationHarness:
    """Orchestrates V2.0 real-world voice identity evaluation.

    Uses the existing Avni pipeline without modification:
        EnrollmentService -> ProfileStore -> VoiceCapability -> SpeechT5
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.data_dir = Path(config.data_dir)
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.result = ExperimentResult(
            experiment_id=config.experiment_id,
            timestamp=config.timestamp,
            config=asdict(config),
        )

    def _load_and_prepare_audio(self, file_path: Path) -> Tuple[bytes, Dict]:
        """Load a WAV file and resample to 16kHz mono if needed."""
        with open(file_path, "rb") as f:
            raw_bytes = f.read()

        info = get_wav_info(raw_bytes)
        prepared = resample_wav_to_16k(raw_bytes)
        prepared_info = get_wav_info(prepared)

        return prepared, {
            "original": info,
            "prepared": prepared_info,
            "hash": hash_audio(prepared),
        }

    def discover_speaker_files(
        self, speaker_id: str
    ) -> Dict[str, List[Path]]:
        """Find enrollment and evaluation WAV files for a speaker."""
        speaker_dir = self.data_dir / speaker_id
        files = {"enrollment": [], "evaluation": []}

        for role in ["enrollment", "evaluation"]:
            role_dir = speaker_dir / role
            if role_dir.is_dir():
                wavs = sorted(role_dir.glob("*.wav"))
                files[role] = wavs
                logger.info(
                    "Found %d %s files for %s", len(wavs), role, speaker_id
                )

        return files

    def run_representation_experiment(
        self,
        extractor,
        speaker_id: str,
        enrollment_files: List[Path],
        evaluation_files: List[Path],
    ) -> Dict[str, Any]:
        """Experiment A/B: Representation consistency and separation.

        Measures whether the neural extractor produces consistent
        representations for the same speaker and distinct representations
        for different speakers.
        """
        results = {"speaker_id": speaker_id, "metrics": []}

        # Prepare enrollment audio
        enrollment_audio = []
        for f in enrollment_files:
            prepared, info = self._load_and_prepare_audio(f)
            enrollment_audio.append(prepared)
            self.result.samples.append({
                "sample_id": f.stem,
                "speaker_id": speaker_id,
                "role": "enrollment",
                "file_path": str(f),
                "audio_hash": info["hash"],
                "duration_seconds": info["prepared"]["duration_seconds"],
                "sample_rate": info["prepared"]["sample_rate"],
                "channels": info["prepared"]["channels"],
            })

        # Prepare evaluation audio
        eval_audio = []
        for f in evaluation_files:
            prepared, info = self._load_and_prepare_audio(f)
            eval_audio.append(prepared)
            self.result.samples.append({
                "sample_id": f.stem,
                "speaker_id": speaker_id,
                "role": "evaluation",
                "file_path": str(f),
                "audio_hash": info["hash"],
                "duration_seconds": info["prepared"]["duration_seconds"],
                "sample_rate": info["prepared"]["sample_rate"],
                "channels": info["prepared"]["channels"],
            })

        # Extract enrollment representation
        t0 = time.perf_counter()
        enrollment_rep = extractor.extract(enrollment_audio)
        extract_latency = time.perf_counter() - t0

        results["enrollment_rep_id"] = enrollment_rep.representation_id
        results["enrollment_rep_version"] = enrollment_rep.version
        results["extract_latency_sec"] = round(extract_latency, 3)

        # Experiment A: Consistency — compare enrollment rep to each eval sample
        for idx, eval_sample in enumerate(eval_audio):
            eval_rep = extractor.extract([eval_sample])
            sim = extractor.similarity(enrollment_rep, eval_rep)
            metric = {
                "metric_name": "representation_consistency",
                "speaker_id": speaker_id,
                "eval_sample_idx": idx,
                "similarity": round(sim, 4),
            }
            results["metrics"].append(metric)
            self.result.metrics.append(metric)
            logger.info(
                "Consistency %s eval[%d]: %.4f", speaker_id, idx, sim
            )

        results["enrollment_representation"] = enrollment_rep
        return results

    def run_cross_speaker_separation(
        self,
        extractor,
        rep_results: Dict[str, Dict],
    ) -> List[Dict[str, Any]]:
        """Experiment B: Cross-speaker separation.

        Compares enrollment representations across different speakers.
        """
        metrics = []
        speaker_ids = list(rep_results.keys())

        for i in range(len(speaker_ids)):
            for j in range(i + 1, len(speaker_ids)):
                sid_a = speaker_ids[i]
                sid_b = speaker_ids[j]
                rep_a = rep_results[sid_a]["enrollment_representation"]
                rep_b = rep_results[sid_b]["enrollment_representation"]
                sim = extractor.similarity(rep_a, rep_b)
                metric = {
                    "metric_name": "cross_speaker_separation",
                    "speaker_a_id": sid_a,
                    "speaker_b_id": sid_b,
                    "similarity": round(sim, 4),
                }
                metrics.append(metric)
                self.result.metrics.append(metric)
                logger.info(
                    "Separation %s vs %s: %.4f", sid_a, sid_b, sim
                )

        return metrics

    def run_end_to_end_identity(
        self,
        extractor,
        rep_results: Dict[str, Dict],
        enrollment_files: Dict[str, List[Path]],
    ) -> Dict[str, Any]:
        """Experiments C/D/E/F: Full pipeline evaluation.

        Enroll -> Persist -> Reload -> Resolve -> Generate -> Measure
        """
        import tempfile
        from src.enrollment.contracts import AudioSample, EnrollmentRequest
        from src.enrollment.enrollment_service import EnrollmentService
        from src.representation.base import VoiceRepresentation
        from src.profiles.consent import ConsentRecord, ConsentStatus, ProvenanceRecord
        from src.profiles.voice_profile import VoiceIdentityProfile
        from src.profiles.profile_store import ProfileStore
        from src.capabilities.voice.capability import VoiceCapability
        from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry
        from src.adapters.tts.speecht5_adapter import SpeechT5TTSAdapter
        from src.contracts.voice import VoiceRequest

        profiles_dir = self.output_dir / "profiles"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        generated_dir = self.output_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        store = ProfileStore(profiles_dir)
        enrollment_service = EnrollmentService(representation_extractor=extractor)

        e2e_results = {}

        # Step 1-2: Enroll and persist each speaker
        for speaker_id, files in enrollment_files.items():
            if speaker_id not in rep_results:
                continue

            logger.info("E2E: Enrolling %s", speaker_id)

            # Prepare audio for enrollment
            prepared_files = []
            temp_dir = self.output_dir / "temp_enrollment"
            temp_dir.mkdir(parents=True, exist_ok=True)

            for idx, f in enumerate(files):
                prepared, info = self._load_and_prepare_audio(f)
                temp_path = temp_dir / f"{speaker_id}_prep_{idx}.wav"
                with open(temp_path, "wb") as out:
                    out.write(prepared)
                prepared_files.append(temp_path)

            # Enroll through the real pipeline
            audio_samples = [
                AudioSample(
                    file_path=fp,
                    source_id=f"{speaker_id}_consent",
                    consent_granted=True,
                )
                for fp in prepared_files
            ]

            req = EnrollmentRequest(
                identity_id=speaker_id,
                samples=audio_samples,
                provenance={"experiment": self.config.experiment_id},
            )

            enroll_result = enrollment_service.enroll(req)
            if not enroll_result.is_success:
                error_msg = f"Enrollment failed for {speaker_id}: {enroll_result.errors}"
                self.result.errors.append(error_msg)
                logger.error(error_msg)
                continue

            # Build and persist profile
            profile = VoiceIdentityProfile(
                identity_id=speaker_id,
                representation=VoiceRepresentation(
                    representation_id="neural_xvector_v1.0",
                    version="1.0",
                    data=enroll_result.representation_data,
                    metadata=enroll_result.metadata.get("representation", {}),
                ),
                consent=ConsentRecord(
                    source_id=f"{speaker_id}_consent",
                    status=ConsentStatus.ACTIVE,
                ),
                provenance=ProvenanceRecord(
                    extractor_id="neural_xvector",
                    extractor_version="1.0",
                    sample_count=len(prepared_files),
                    source_sample_hashes=[
                        hash_audio(open(fp, "rb").read())
                        for fp in prepared_files
                    ],
                    environment_info={
                        "experiment": self.config.experiment_id,
                    },
                ),
            )

            store.save(profile)
            logger.info("E2E: Profile persisted for %s", speaker_id)

            # Step 3: Reload (tests persistence roundtrip)
            reloaded = store.load(speaker_id)
            assert reloaded.identity_id == speaker_id
            assert reloaded.representation.is_valid
            logger.info("E2E: Profile reloaded for %s", speaker_id)

            e2e_results[speaker_id] = {
                "enrollment_status": "SUCCESS",
                "profile_persisted": True,
                "profile_reloaded": True,
                "generated_samples": [],
            }

        # Step 4-6: Generate speech through the full capability path
        renderer_reg = RendererRegistry()
        renderer_reg.register(SpeechT5TTSAdapter())

        capability = VoiceCapability(
            identity_registry=IdentityRegistry(),
            renderer_registry=renderer_reg,
            profile_store=store,
        )

        for speaker_id in e2e_results:
            logger.info("E2E: Generating speech for %s", speaker_id)

            for text_idx, text in enumerate(self.config.test_texts):
                t0 = time.perf_counter()
                try:
                    response = capability.synthesize(
                        VoiceRequest(
                            text=text,
                            identity_id=speaker_id,
                            request_id=f"{self.config.experiment_id}_{speaker_id}_{text_idx}",
                        )
                    )
                    latency = time.perf_counter() - t0

                    # Save generated audio
                    out_path = generated_dir / f"{speaker_id}_text{text_idx}.wav"
                    with open(out_path, "wb") as f:
                        f.write(response.audio_bytes)

                    gen_info = get_wav_info(response.audio_bytes)

                    e2e_results[speaker_id]["generated_samples"].append({
                        "text_idx": text_idx,
                        "text": text,
                        "file": str(out_path),
                        "duration_seconds": gen_info.get("duration_seconds", 0),
                        "latency_sec": round(latency, 3),
                        "audio_hash": hash_audio(response.audio_bytes),
                    })

                    self.result.generated_files.append(str(out_path))
                    logger.info(
                        "E2E: Generated %s text[%d] in %.2fs (%.1fs audio)",
                        speaker_id, text_idx, latency,
                        gen_info.get("duration_seconds", 0),
                    )

                except Exception as exc:
                    error_msg = f"Generation failed {speaker_id} text[{text_idx}]: {exc}"
                    self.result.errors.append(error_msg)
                    logger.error(error_msg)

        # Step 7: Measure generated identity retention
        for speaker_id in e2e_results:
            gen_dir = generated_dir
            gen_files = sorted(gen_dir.glob(f"{speaker_id}_text*.wav"))

            for gen_file in gen_files:
                prepared_gen, _ = self._load_and_prepare_audio(gen_file)

                # Compare generated to real evaluation samples
                eval_files = self.discover_speaker_files(speaker_id).get("evaluation", [])
                for eval_file in eval_files:
                    prepared_eval, _ = self._load_and_prepare_audio(eval_file)
                    gen_rep = extractor.extract([prepared_gen])
                    eval_rep = extractor.extract([prepared_eval])
                    sim = extractor.similarity(gen_rep, eval_rep)

                    metric = {
                        "metric_name": "generated_identity_retention",
                        "speaker_id": speaker_id,
                        "generated_file": gen_file.name,
                        "reference_file": eval_file.name,
                        "similarity": round(sim, 4),
                    }
                    self.result.metrics.append(metric)

                # Cross-identity: compare generated A to real B
                for other_id in e2e_results:
                    if other_id == speaker_id:
                        continue
                    other_eval = self.discover_speaker_files(other_id).get("evaluation", [])
                    for other_file in other_eval:
                        prepared_other, _ = self._load_and_prepare_audio(other_file)
                        gen_rep = extractor.extract([prepared_gen])
                        other_rep = extractor.extract([prepared_other])
                        sim = extractor.similarity(gen_rep, other_rep)

                        metric = {
                            "metric_name": "cross_identity_generation",
                            "generated_speaker": speaker_id,
                            "reference_speaker": other_id,
                            "generated_file": gen_file.name,
                            "similarity": round(sim, 4),
                        }
                        self.result.metrics.append(metric)

        return e2e_results

    def finalize(self) -> ExperimentResult:
        """Compute summary statistics and save results."""
        metrics_by_name = {}
        for m in self.result.metrics:
            name = m["metric_name"]
            if name not in metrics_by_name:
                metrics_by_name[name] = []
            metrics_by_name[name].append(m["similarity"])

        summary = {}
        for name, values in metrics_by_name.items():
            summary[name] = {
                "count": len(values),
                "mean": round(sum(values) / len(values), 4) if values else 0,
                "min": round(min(values), 4) if values else 0,
                "max": round(max(values), 4) if values else 0,
            }

        self.result.summary = summary
        self.result.errors_count = len(self.result.errors)

        # Save
        results_path = self.output_dir / f"{self.config.experiment_id}_results.json"
        self.result.save(results_path)

        return self.result
