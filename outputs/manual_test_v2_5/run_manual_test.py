import os
import sys
import io
import wave
import time
from pathlib import Path
import numpy as np

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.contracts.voice import VoiceRequest, VoiceConversionRequest
from src.contracts.renderer import RenderResult
from src.representation.neural_extractor import NeuralSpeakerExtractor
from src.representation.base import VoiceRepresentation
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.consent import ConsentRecord, ProvenanceRecord, ConsentStatus
from src.profiles.profile_store import ProfileStore
from src.enrollment.contracts import AudioSample, EnrollmentRequest
from src.enrollment.enrollment_service import EnrollmentService
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, ConverterRegistry, RendererRegistry
from src.adapters.voice_conversion.acoustic_vc_adapter import AcousticVCAdapter
from src.adapters.voice_conversion.speecht5_vc_adapter import SpeechT5VCAdapter
from src.adapters.tts.speecht5_adapter import SpeechT5TTSAdapter
from src.adapters.tts.edge_tts_adapter import EdgeTTSAdapter

output_dir = Path("outputs/manual_test_v2_5")
output_dir.mkdir(parents=True, exist_ok=True)

def generate_speech_wav(f0=120.0, duration=2.0, sample_rate=16000, modulation=False):
    """Generates rich harmonic audio simulating speech formants."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    pitch_mod = 1.0 + (0.08 * np.sin(2 * np.pi * 3.0 * t)) if modulation else 1.0
    sig = 0.5 * np.sin(2 * np.pi * f0 * pitch_mod * t) + \
          0.3 * np.sin(2 * np.pi * 2 * f0 * pitch_mod * t) + \
          0.15 * np.sin(2 * np.pi * 3 * f0 * pitch_mod * t) + \
          0.05 * np.sin(2 * np.pi * 4 * f0 * pitch_mod * t)
          
    envelope = (np.sin(np.pi * t / duration) ** 1.2) * (0.8 + 0.2 * np.sin(2 * np.pi * 4 * t))
    sig = (sig * envelope * 32767).astype(np.int16)
    
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(sig.tobytes())
    return buf.getvalue()

def save_wav(filename, audio_bytes):
    filepath = output_dir / filename
    filepath.write_bytes(audio_bytes)
    print(f"  [SAVED] {filepath} ({len(audio_bytes)} bytes)")
    return filepath

print("\n" + "=" * 60)
print("1. GENERATING ENROLLMENT SAMPLES FOR TARGET IDENTITY (Aria)")
print("=" * 60)
aria_sample1 = generate_speech_wav(f0=210.0, duration=1.8, modulation=True)
aria_sample2 = generate_speech_wav(f0=215.0, duration=1.8, modulation=True)
sample1_path = save_wav("target_aria_enroll_1.wav", aria_sample1)
sample2_path = save_wav("target_aria_enroll_2.wav", aria_sample2)

print("\n" + "=" * 60)
print("2. ENROLLING TARGET IDENTITY INTO AVNI PROFILE STORE")
print("=" * 60)
extractor = NeuralSpeakerExtractor()
enroll_service = EnrollmentService(representation_extractor=extractor)
enroll_req = EnrollmentRequest(
    identity_id="target-aria",
    samples=[
        AudioSample(file_path=sample1_path, source_id="authorized-aria"),
        AudioSample(file_path=sample2_path, source_id="authorized-aria"),
    ],
    provenance={"institution": "Aryntra R&D", "channel": "manual_test"}
)
enroll_result = enroll_service.enroll(enroll_req)
print(f"  Enrollment Status: {enroll_result.status.value}")
print(f"  Extracted 512-dim Representation Vector: {len(enroll_result.representation_data)} bytes")

rep = VoiceRepresentation(
    representation_id="neural_xvector_aria_v1",
    version=enroll_result.representation_version,
    data=enroll_result.representation_data,
    metadata=enroll_result.metadata.get("representation", {})
)
profile = VoiceIdentityProfile(
    identity_id="target-aria",
    representation=rep,
    consent=ConsentRecord(
        source_id="authorized-aria",
        status=ConsentStatus.ACTIVE,
        scope="voice_synthesis_and_conversion"
    ),
    provenance=ProvenanceRecord(
        extractor_id=extractor.extractor_id,
        extractor_version=extractor.version,
        sample_count=2,
        source_sample_hashes=["hash_aria_1", "hash_aria_2"]
    )
)
store = ProfileStore(storage_dir=output_dir / "profiles")
saved_path = store.save(profile)
print(f"  Persisted profile JSON to disk: {saved_path}")

print("\n" + "=" * 60)
print("3. GENERATING SOURCE USER SPEECH ('User Utterance')")
print("=" * 60)
source_audio = generate_speech_wav(f0=110.0, duration=2.5, modulation=True)
source_path = save_wav("source_speech_user.wav", source_audio)

print("\n" + "=" * 60)
print("4. INITIALIZING VOICE CAPABILITY")
print("=" * 60)
converters = ConverterRegistry()
converters.register(AcousticVCAdapter())
converters.register(SpeechT5VCAdapter())

renderers = RendererRegistry()
renderers.register(SpeechT5TTSAdapter())
renderers.register(EdgeTTSAdapter())

capability = VoiceCapability(
    renderer_registry=renderers,
    converter_registry=converters,
    profile_store=store
)
print("  VoiceCapability ready with dual registries (Renderers + Converters).")

print("\n" + "=" * 60)
print("5. TEST: SPEECH-TO-SPEECH VOICE CONVERSION")
print("   Source Speech (User, 110Hz) -> Target Identity (Aria, 210Hz)")
print("=" * 60)
t0 = time.perf_counter()
vc_request = VoiceConversionRequest(
    target_identity_id="target-aria",
    source_audio_bytes=source_audio,
    source_sample_rate=16000,
    request_id="manual-vc-req-001"
)
vc_response = capability.convert(vc_request)
vc_lat = time.perf_counter() - t0

print(f"  Voice Conversion Complete!")
print(f"  Latency: {vc_lat*1000:.2f} ms")
print(f"  Converter Engine: {vc_response.metadata.get('converter_id')}")
print(f"  Fallback Triggered: {vc_response.metadata.get('fallback_used')}")
print(f"  Output Audio Duration: {vc_response.duration_seconds:.3f} s (Source: 2.500 s)")
save_wav("output_voice_converted_to_aria.wav", vc_response.audio_bytes)

print("\n" + "=" * 60)
print("6. TEST: TEXT-TO-SPEECH MANIFESTATION (SAME IDENTITY)")
print("   Text -> Target Identity (Aria)")
print("=" * 60)
t0 = time.perf_counter()
tts_request = VoiceRequest(
    identity_id="target-aria",
    text="Hello, I am Aria. My persistent identity is now active across speech and text.",
    request_id="manual-tts-req-001"
)
tts_response = capability.synthesize(tts_request)
tts_lat = time.perf_counter() - t0

print(f"  TTS Synthesis Complete!")
print(f"  Latency: {tts_lat*1000:.2f} ms")
print(f"  Renderer Engine: {tts_response.metadata.get('renderer_id')}")
print(f"  Output Audio Duration: {tts_response.duration_seconds:.3f} s")
save_wav("output_tts_manifested_as_aria.wav", tts_response.audio_bytes)

print("\n" + "=" * 60)
print("ALL MANUAL TESTS SUCCEEDED!")
print("=" * 60)
