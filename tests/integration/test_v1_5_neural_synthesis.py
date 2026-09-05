"""End-to-end neural speaker conditioning integration tests for Aryntra Avni V1.5."""

import io
import math
import struct
import tempfile
import wave
from pathlib import Path

import pytest
import torch

from src import VoiceRequest
from src.enrollment.contracts import AudioSample, EnrollmentRequest
from src.enrollment.enrollment_service import EnrollmentService
from src.representation.neural_extractor import NeuralSpeakerExtractor, _bytes_to_embedding
from src.representation.base import VoiceRepresentation
from src.profiles.consent import ConsentRecord, ConsentStatus, ProvenanceRecord
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.profile_store import ProfileStore
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry
from src.adapters.tts.speecht5_adapter import SpeechT5TTSAdapter


def _create_sine_wav(path: Path, freqs: list, duration_sec: float = 2.0, sample_rate: int = 16000) -> Path:
    n_frames = int(sample_rate * duration_sec)
    samples = []
    for i in range(n_frames):
        t = i / sample_rate
        val = sum(math.sin(2 * math.pi * f * t) / (idx + 1) for idx, f in enumerate(freqs))
        val = max(-1.0, min(1.0, val * 0.5))
        samples.append(int(val * 32767))

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *samples))
    return path


def test_v1_5_neural_synthesis_end_to_end_lifecycle():
    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        profiles_dir = tmp_dir / "profiles"
        profiles_dir.mkdir()

        # Step 1: Prep Authorized Voice Samples
        # Speaker A (harmonic profile based on 110Hz fundamental)
        s1_a = _create_sine_wav(tmp_dir / "speaker_a_sample1.wav", [110, 220, 330])
        s2_a = _create_sine_wav(tmp_dir / "speaker_a_sample2.wav", [110, 220, 330])

        # Speaker B (harmonic profile based on 250Hz fundamental)
        s1_b = _create_sine_wav(tmp_dir / "speaker_b_sample1.wav", [250, 500, 750])
        s2_b = _create_sine_wav(tmp_dir / "speaker_b_sample2.wav", [250, 500, 750])

        # Step 2: Extract & Enroll
        extractor = NeuralSpeakerExtractor()
        enrollment_service = EnrollmentService(representation_extractor=extractor)

        req_a = EnrollmentRequest(
            identity_id="neural_user_alpha",
            samples=[
                AudioSample(file_path=s1_a, source_id="user_alpha_grant"),
                AudioSample(file_path=s2_a, source_id="user_alpha_grant"),
            ],
        )
        req_b = EnrollmentRequest(
            identity_id="neural_user_beta",
            samples=[
                AudioSample(file_path=s1_b, source_id="user_beta_grant"),
                AudioSample(file_path=s2_b, source_id="user_beta_grant"),
            ],
        )

        res_a = enrollment_service.enroll(req_a)
        res_b = enrollment_service.enroll(req_b)

        assert res_a.is_success
        assert res_b.is_success
        assert len(res_a.representation_data) == 512 * 4  # 512 float32 = 2048 bytes
        assert len(res_b.representation_data) == 512 * 4

        # Step 3: Persist Profile Store
        store = ProfileStore(profiles_dir)

        prof_a = VoiceIdentityProfile(
            identity_id="neural_user_alpha",
            representation=VoiceRepresentation(
                representation_id="neural_xvector_v1.0",
                version="1.0",
                data=res_a.representation_data,
                metadata=res_a.metadata.get("representation", {}),
            ),
            consent=ConsentRecord(source_id="user_alpha_grant", status=ConsentStatus.ACTIVE),
            provenance=ProvenanceRecord(
                extractor_id="neural_xvector",
                extractor_version="1.0",
                sample_count=2,
            ),
        )

        prof_b = VoiceIdentityProfile(
            identity_id="neural_user_beta",
            representation=VoiceRepresentation(
                representation_id="neural_xvector_v1.0",
                version="1.0",
                data=res_b.representation_data,
                metadata=res_b.metadata.get("representation", {}),
            ),
            consent=ConsentRecord(source_id="user_beta_grant", status=ConsentStatus.ACTIVE),
            provenance=ProvenanceRecord(
                extractor_id="neural_xvector",
                extractor_version="1.0",
                sample_count=2,
            ),
        )

        store.save(prof_a)
        store.save(prof_b)

        # Confirm profiles are written to disk
        assert store.exists("neural_user_alpha")
        assert store.exists("neural_user_beta")

        # Step 4: System Restart Simulation (Clear registries)
        renderer_reg = RendererRegistry()
        renderer_reg.register(SpeechT5TTSAdapter())

        capability = VoiceCapability(
            identity_registry=IdentityRegistry(),
            renderer_registry=renderer_reg,
            profile_store=store,
        )

        # Step 5: Render and Condition on Identity Alpha
        resp_a = capability.synthesize(
            VoiceRequest(
                text="Hello from Avni voice identity alpha.",
                identity_id="neural_user_alpha",
                request_id="req_neural_01",
            )
        )

        # Step 6: Render and Condition on Identity Beta
        resp_b = capability.synthesize(
            VoiceRequest(
                text="Hello from Avni voice identity alpha.",  # identical text, different speaker conditioning
                identity_id="neural_user_beta",
                request_id="req_neural_02",
            )
        )

        assert resp_a.audio_format == "wav"
        assert resp_b.audio_format == "wav"
        assert len(resp_a.audio_bytes) > 1000
        assert len(resp_b.audio_bytes) > 1000

        # Step 7: Mathematically verify identity-conditioning uniqueness
        # Load output waveform samples and check difference
        with wave.open(io.BytesIO(resp_a.audio_bytes), "rb") as wf:
            raw_a = wf.readframes(wf.getnframes())
            samples_a = list(struct.unpack(f"<{len(raw_a)//2}h", raw_a))

        with wave.open(io.BytesIO(resp_b.audio_bytes), "rb") as wf:
            raw_b = wf.readframes(wf.getnframes())
            samples_b = list(struct.unpack(f"<{len(raw_b)//2}h", raw_b))

        # Because different speaker embeddings condition prosody, cadence, and duration differently,
        # they will output distinctly sized audio sample sizes or waveforms.
        if len(samples_a) == len(samples_b):
            wave_diff = sum(abs(sa - sb) for sa, sb in zip(samples_a, samples_b))
            assert wave_diff > 0.0, "Conditioning did not create a different waveform!"
        else:
            # Different lengths implies distinct duration properties due to conditioning
            assert len(samples_a) != len(samples_b)
