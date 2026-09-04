"""Aryntra Avni — V1.0 NAV Voice Identity Lifecycle Demo.

Demonstrates:
1. Enrolling authorized audio samples into a Voice Representation.
2. Persisting the VoiceIdentityProfile with Consent & Provenance.
3. Synthesizing speech as NAV by requesting the enrolled identity ID.
"""

import math
import struct
import sys
import tempfile
import wave
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import VoiceRequest, create_default_voice_capability
from src.enrollment.contracts import AudioSample, EnrollmentRequest
from src.enrollment.enrollment_service import EnrollmentService
from src.representation.acoustic_extractor import AcousticFeatureExtractor
from src.representation.base import VoiceRepresentation
from src.profiles.consent import ConsentRecord, ConsentStatus, ProvenanceRecord
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.profile_store import ProfileStore


def _create_sample_audio(path: Path, freq: float) -> Path:
    sample_rate = 16000
    duration_sec = 2.0
    n_frames = int(sample_rate * duration_sec)
    samples = [int(16000 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n_frames)]
    frames = struct.pack(f"<{n_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path


def main():
    print("=" * 60)
    print("Aryntra Avni — V1.0 NAV Voice Identity Demo")
    print("=" * 60)

    artifacts_dir = Path(__file__).resolve().parents[1] / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    profiles_dir = Path(__file__).resolve().parents[1] / "data" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        print("\n[Step 1] Recording 2 authorized audio samples...")
        s1 = _create_sample_audio(tmp / "rec_1.wav", freq=440.0)
        s2 = _create_sample_audio(tmp / "rec_2.wav", freq=445.0)

        print("[Step 2] Enrolling voice recordings into Representation...")
        extractor = AcousticFeatureExtractor()
        enroll_service = EnrollmentService(representation_extractor=extractor)
        enroll_req = EnrollmentRequest(
            identity_id="dr_elena_demo",
            samples=[
                AudioSample(file_path=s1, source_id="dr_elena", consent_granted=True),
                AudioSample(file_path=s2, source_id="dr_elena", consent_granted=True),
            ],
        )
        enroll_res = enroll_service.enroll(enroll_req)
        assert enroll_res.is_success, f"Enrollment failed: {enroll_res.errors}"
        print(f"  -> Extracted {len(enroll_res.representation_data)} bytes representation ({enroll_res.representation_version})")

        print("[Step 3] Persisting VoiceIdentityProfile with Consent & Lineage...")
        store = ProfileStore(profiles_dir)
        profile = VoiceIdentityProfile(
            identity_id="dr_elena_demo",
            representation=VoiceRepresentation(
                representation_id="acoustic_stats_v1.0",
                version="1.0",
                data=enroll_res.representation_data,
                metadata=enroll_res.metadata.get("representation", {}),
            ),
            consent=ConsentRecord(source_id="dr_elena", status=ConsentStatus.ACTIVE),
            provenance=ProvenanceRecord(
                extractor_id="acoustic_stats",
                extractor_version="1.0",
                sample_count=2,
            ),
        )
        saved_path = store.save(profile)
        print(f"  -> Profile saved to {saved_path}")

    print("\n[Step 4] Initializing NAV VoiceCapability...")
    capability = create_default_voice_capability(profiles_dir=profiles_dir)

    print("[Step 5] NAV synthesizing speech via persistent identity 'dr_elena_demo'...")
    request = VoiceRequest(
        text="Hello NAV. This is Aryntra Avni speaking from a persistent, reusable voice identity profile.",
        identity_id="dr_elena_demo",
        request_id="demo_req_001",
    )
    response = capability.synthesize(request)

    out_file = artifacts_dir / "v1_nav_profile_output.mp3"
    out_file.write_bytes(response.audio_bytes)

    print(f"\nSUCCESS: Generated {len(response.audio_bytes)} bytes audio -> {out_file}")
    print(f"Metadata: {response.metadata}")
    print("=" * 60)


if __name__ == "__main__":
    main()
