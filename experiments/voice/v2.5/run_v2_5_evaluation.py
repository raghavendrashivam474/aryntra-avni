"""V2.5 Evaluation Benchmark: Testing Voice Conversion & Dual Manifestation.

Evaluates:
- Experiment A: Same-Speaker conversion
- Experiment B: Cross-Speaker conversion
- Experiment C: Multi-Target divergence
- Experiment D: Persistence through disk reload
- Experiment E: Dual Manifestation (Same Identity -> TTS and VC)
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import io
import json
import time
import wave
import struct
import tempfile
import numpy as np

from src.contracts.voice import VoiceRequest, VoiceConversionRequest
from src.contracts.renderer import RenderResult, TTSRenderer
from src.representation.neural_extractor import NeuralSpeakerExtractor
from src.representation.base import VoiceRepresentation
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.consent import ConsentRecord, ProvenanceRecord, ConsentStatus
from src.profiles.profile_store import ProfileStore
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, ConverterRegistry, RendererRegistry
from src.adapters.voice_conversion.acoustic_vc_adapter import AcousticVCAdapter


class MockNeuralTTSAdapter(TTSRenderer):
    """Deterministic TTS renderer for testing dual manifestation."""
    @property
    def renderer_id(self) -> str:
        return "speecht5"

    def is_available(self) -> bool:
        return True

    def render(self, text, voice_config, context=None):
        duration_sec = max(0.5, len(text) * 0.06)
        sample_rate = 16000
        t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
        # Synthetic speech wave conditioned on representation
        rep_bytes = voice_config.get("representation_data", b"")
        f0 = 120.0 + (sum(rep_bytes) % 60)
        signal_data = (np.sin(2 * np.pi * f0 * t) * 32767).astype(np.int16)
        
        out_buf = io.BytesIO()
        with wave.open(out_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(signal_data.tobytes())
            
        return RenderResult(
            audio_bytes=out_buf.getvalue(),
            audio_format="wav",
            sample_rate=sample_rate,
            duration_seconds=duration_sec,
            metadata={"engine": "mock_neural_tts", "f0": f0}
        )


def make_synthetic_speech(f0: float = 140.0, duration: float = 1.2, sample_rate: int = 16000) -> bytes:
    """Generate synthetic speech audio with harmonics and envelope."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # Fundamental + harmonics for speech-like timbre
    sig = 0.6 * np.sin(2 * np.pi * f0 * t) + \
          0.3 * np.sin(2 * np.pi * 2 * f0 * t) + \
          0.1 * np.sin(2 * np.pi * 3 * f0 * t)
    # Speech envelope (rise, sustain, decay)
    env = np.sin(np.pi * t / duration) ** 1.5
    sig = (sig * env * 32767).astype(np.int16)
    
    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(sig.tobytes())
    return out_buf.getvalue()


def compute_vector_similarity(rep_a: VoiceRepresentation, rep_b: VoiceRepresentation) -> float:
    """Compute cosine similarity mapped to [0, 1]."""
    v_a = np.frombuffer(rep_a.data, dtype=np.float32)
    v_b = np.frombuffer(rep_b.data, dtype=np.float32)
    norm_a = np.linalg.norm(v_a)
    norm_b = np.linalg.norm(v_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    dot = float(np.dot(v_a, v_b))
    cos_sim = dot / (norm_a * norm_b)
    return float(max(0.0, min(1.0, (cos_sim + 1.0) / 2.0)))


def run_benchmark():
    print("=" * 70)
    print("RUNNING V2.5 EVALUATION & BENCHMARK SUITE")
    print("=" * 70)
    
    results = {}
    extractor = NeuralSpeakerExtractor()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_dir = Path(tmp_dir)
        store = ProfileStore(storage_dir=storage_dir)
        
        # 1. Enroll Target Identity Alpha (f0 ~ 110Hz) and Beta (f0 ~ 200Hz)
        print("\n[Phase 1] Enrolling persistent identities Alpha and Beta...")
        raw_alpha_1 = make_synthetic_speech(f0=110.0, duration=1.5)
        raw_alpha_2 = make_synthetic_speech(f0=112.0, duration=1.5)
        rep_alpha = extractor.extract([raw_alpha_1, raw_alpha_2])
        
        profile_alpha = VoiceIdentityProfile(
            identity_id="identity-alpha",
            representation=rep_alpha,
            consent=ConsentRecord(source_id="spk-alpha", status=ConsentStatus.ACTIVE, scope="synthesis_and_vc"),
            provenance=ProvenanceRecord(extractor_id=extractor.extractor_id, extractor_version=extractor.version, sample_count=2, source_sample_hashes=["h1", "h2"])
        )
        store.save(profile_alpha)
        
        raw_beta_1 = make_synthetic_speech(f0=200.0, duration=1.5)
        raw_beta_2 = make_synthetic_speech(f0=205.0, duration=1.5)
        rep_beta = extractor.extract([raw_beta_1, raw_beta_2])
        
        profile_beta = VoiceIdentityProfile(
            identity_id="identity-beta",
            representation=rep_beta,
            consent=ConsentRecord(source_id="spk-beta", status=ConsentStatus.ACTIVE, scope="synthesis_and_vc"),
            provenance=ProvenanceRecord(extractor_id=extractor.extractor_id, extractor_version=extractor.version, sample_count=2, source_sample_hashes=["h3", "h4"])
        )
        store.save(profile_beta)
        
        # Baseline cosine similarity between Alpha and Beta representations
        inter_id_similarity = compute_vector_similarity(rep_alpha, rep_beta)
        print(f"  Baseline Identity Distinction: Sim(Alpha, Beta) = {inter_id_similarity:.4f}")
        results["inter_identity_similarity"] = round(inter_id_similarity, 4)
        
        # Setup VoiceCapability
        converters = ConverterRegistry()
        converters.register(AcousticVCAdapter())
        renderers = RendererRegistry()
        renderers.register(MockNeuralTTSAdapter())
        
        capability = VoiceCapability(
            renderer_registry=renderers,
            converter_registry=converters,
            profile_store=store
        )
        
        # Source speech from an external speaker Gamma (f0 ~ 150Hz)
        source_speech = make_synthetic_speech(f0=150.0, duration=1.8)
        
        # ---------------------------------------------------------
        # Experiment A: Same-speaker conversion stability
        # ---------------------------------------------------------
        print("\n--- Experiment A: Same-Speaker Conversion ---")
        t0 = time.perf_counter()
        resp_a = capability.convert(VoiceConversionRequest(
            target_identity_id="identity-alpha",
            source_audio_bytes=raw_alpha_1
        ))
        lat_a = time.perf_counter() - t0
        timing_diff_a = abs(resp_a.duration_seconds - 1.5)
        print(f"  Exp A: Output duration = {resp_a.duration_seconds:.3f}s (Source = 1.5s, Diff = {timing_diff_a:.4f}s)")
        print(f"  Exp A: Latency = {lat_a*1000:.2f}ms")
        results["exp_a_same_speaker"] = {
            "source_duration": 1.5,
            "output_duration": round(resp_a.duration_seconds, 3),
            "timing_drift_sec": round(timing_diff_a, 4),
            "latency_ms": round(lat_a * 1000, 2)
        }
        
        # ---------------------------------------------------------
        # Experiment B: Cross-speaker conversion
        # ---------------------------------------------------------
        print("\n--- Experiment B: Cross-Speaker Conversion ---")
        t0 = time.perf_counter()
        resp_b = capability.convert(VoiceConversionRequest(
            target_identity_id="identity-alpha",
            source_audio_bytes=source_speech
        ))
        lat_b = time.perf_counter() - t0
        timing_diff_b = abs(resp_b.duration_seconds - 1.8)
        print(f"  Exp B (Gamma -> Alpha): Output duration = {resp_b.duration_seconds:.3f}s (Source = 1.8s)")
        print(f"  Exp B: Latency = {lat_b*1000:.2f}ms | Target = {resp_b.metadata['identity_id']}")
        results["exp_b_cross_speaker"] = {
            "source_duration": 1.8,
            "output_duration": round(resp_b.duration_seconds, 3),
            "timing_drift_sec": round(timing_diff_b, 4),
            "latency_ms": round(lat_b * 1000, 2)
        }
        
        # ---------------------------------------------------------
        # Experiment C: Multi-Target Divergence
        # ---------------------------------------------------------
        print("\n--- Experiment C: Multiple Target Manifestation ---")
        resp_c_alpha = capability.convert(VoiceConversionRequest(
            target_identity_id="identity-alpha",
            source_audio_bytes=source_speech
        ))
        resp_c_beta = capability.convert(VoiceConversionRequest(
            target_identity_id="identity-beta",
            source_audio_bytes=source_speech
        ))
        
        shift_alpha = resp_c_alpha.metadata.get("shift_factor")
        shift_beta = resp_c_beta.metadata.get("shift_factor")
        print(f"  Exp C: Source manifested as Target Alpha (shift={shift_alpha})")
        print(f"  Exp C: Source manifested as Target Beta (shift={shift_beta})")
        print(f"  Exp C: Are manifestations distinct? {shift_alpha != shift_beta}")
        results["exp_c_multi_target"] = {
            "target_alpha_shift": shift_alpha,
            "target_beta_shift": shift_beta,
            "distinct_manifestation": shift_alpha != shift_beta
        }
        
        # ---------------------------------------------------------
        # Experiment D: Persistence Verification
        # ---------------------------------------------------------
        print("\n--- Experiment D: Persistence Across Simulated Process Reload ---")
        fresh_store = ProfileStore(storage_dir=storage_dir)
        fresh_cap = VoiceCapability(
            renderer_registry=renderers,
            converter_registry=converters,
            profile_store=fresh_store
        )
        assert fresh_store.exists("identity-beta") is True
        resp_d = fresh_cap.convert(VoiceConversionRequest(
            target_identity_id="identity-beta",
            source_audio_bytes=source_speech
        ))
        print(f"  Exp D: Reloaded 'identity-beta' successfully resolved and converted audio!")
        print(f"  Exp D: Output format={resp_d.audio_format}, SR={resp_d.sample_rate}Hz")
        results["exp_d_persistence"] = {
            "reloaded_profile_id": resp_d.metadata["profile_id"],
            "successful_conversion": len(resp_d.audio_bytes) > 0
        }
        
        # ---------------------------------------------------------
        # Experiment E: Dual Manifestation (TTS vs VC on same Identity)
        # ---------------------------------------------------------
        print("\n--- Experiment E: Dual Manifestation (One Identity -> TTS + VC) ---")
        tts_resp = fresh_cap.synthesize(VoiceRequest(
            identity_id="identity-alpha",
            text="Testing dual manifestation for persistent Avni identity."
        ))
        vc_resp = fresh_cap.convert(VoiceConversionRequest(
            target_identity_id="identity-alpha",
            source_audio_bytes=source_speech
        ))
        
        print(f"  Exp E: Same Identity ('{profile_alpha.identity_id}') manifested via:")
        print(f"    1. TTS: {len(tts_resp.audio_bytes)} bytes, duration={tts_resp.duration_seconds:.2f}s, renderer={tts_resp.metadata['renderer_id']}")
        print(f"    2. VC : {len(vc_resp.audio_bytes)} bytes, duration={vc_resp.duration_seconds:.2f}s, converter={vc_resp.metadata['converter_id']}")
        print(f"  Exp E: Representation ID match: {tts_resp.metadata.get('representation_id')} == {vc_resp.metadata.get('representation_id')}")
        results["exp_e_dual_manifestation"] = {
            "identity_id": profile_alpha.identity_id,
            "tts_rendered": len(tts_resp.audio_bytes) > 0,
            "vc_converted": len(vc_resp.audio_bytes) > 0,
            "representation_id": tts_resp.metadata.get("representation_id"),
            "success": tts_resp.metadata.get("representation_id") == vc_resp.metadata.get("representation_id")
        }
        
    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETED SUCCESSFULLY")
    print("=" * 70)
    
    out_path = Path("experiments/voice/v2.5/benchmark_results.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Saved experiment benchmark results to {out_path}")
    return results

if __name__ == "__main__":
    run_benchmark()
