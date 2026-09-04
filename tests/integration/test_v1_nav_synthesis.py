"""Tests for Sprint 4: NAV / TTS Integration with persistent Voice Identity Profiles."""

import math
import struct
import tempfile
import wave
from pathlib import Path
from unittest import TestCase

from src import VoiceRequest, create_default_voice_capability, AvniVoiceError
from src.enrollment.contracts import AudioSample, EnrollmentRequest
from src.enrollment.enrollment_service import EnrollmentService
from src.representation.acoustic_extractor import AcousticFeatureExtractor
from src.representation.base import VoiceRepresentation
from src.profiles.consent import ConsentRecord, ConsentStatus, ProvenanceRecord
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.profile_store import ProfileStore
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry
from src.adapters.tts.edge_tts_adapter import EdgeTTSAdapter
from src.adapters.tts.piper_adapter import PiperTTSAdapter


def _create_wav(path: Path, freq: float = 440.0) -> Path:
    sample_rate = 16000
    n_frames = sample_rate * 2
    samples = [int(16000 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n_frames)]
    frames = struct.pack(f"<{n_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path


class TestV1NAVProfileSynthesis(TestCase):
    """Verify NAV can transparently use persistent voice identity profiles."""

    def test_full_lifecycle_enroll_persist_synthesize(self):
        """Test complete lifecycle: Enroll audio -> Save Profile -> Synthesize via NAV capability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            profiles_dir = tmp_path / "profiles"
            profiles_dir.mkdir()

            # 1. Enroll
            s1 = _create_wav(tmp_path / "sample1.wav", freq=440.0)
            s2 = _create_wav(tmp_path / "sample2.wav", freq=445.0)

            extractor = AcousticFeatureExtractor()
            enrollment_service = EnrollmentService(representation_extractor=extractor)
            enroll_req = EnrollmentRequest(
                identity_id="dr_elena_v1",
                samples=[
                    AudioSample(file_path=s1, source_id="dr_elena"),
                    AudioSample(file_path=s2, source_id="dr_elena"),
                ],
            )
            enroll_res = enrollment_service.enroll(enroll_req)
            self.assertTrue(enroll_res.is_success)

            # 2. Persist Profile
            store = ProfileStore(profiles_dir)
            profile = VoiceIdentityProfile(
                identity_id="dr_elena_v1",
                representation=VoiceRepresentation(
                    representation_id="acoustic_stats_v1.0",
                    version="1.0",
                    data=enroll_res.representation_data,
                ),
                consent=ConsentRecord(source_id="dr_elena", status=ConsentStatus.ACTIVE),
                provenance=ProvenanceRecord(
                    extractor_id="acoustic_stats",
                    extractor_version="1.0",
                    sample_count=2,
                ),
            )
            store.save(profile)

            # 3. Create VoiceCapability with profile store attached
            identity_reg = IdentityRegistry()
            renderer_reg = RendererRegistry()
            renderer_reg.register(PiperTTSAdapter())  # Use local Piper for fast test
            renderer_reg.register(EdgeTTSAdapter())

            capability = VoiceCapability(
                identity_registry=identity_reg,
                renderer_registry=renderer_reg,
                profile_store=store,
            )

            # 4. Synthesize as NAV
            req = VoiceRequest(
                text="Hello NAV, this voice was dynamically resolved from a persistent profile.",
                identity_id="dr_elena_v1",
                request_id="nav_v1_req_001",
            )
            response = capability.synthesize(req)

            self.assertIsNotNone(response.audio_bytes)
            self.assertGreater(len(response.audio_bytes), 100)
            self.assertEqual(response.metadata["identity_id"], "dr_elena_v1")
            self.assertEqual(response.metadata["representation_id"], "acoustic_stats_v1.0")
            self.assertEqual(response.metadata["profile_id"], "dr_elena_v1")

    def test_revoked_consent_blocks_synthesis(self):
        """A profile with revoked consent cannot be synthesized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ProfileStore(tmpdir)
            profile = VoiceIdentityProfile(
                identity_id="revoked_voice",
                representation=VoiceRepresentation(
                    representation_id="rep_v1",
                    version="1.0",
                    data=b"\x00" * 40,
                ),
                consent=ConsentRecord(source_id="user_x", status=ConsentStatus.REVOKED),
                provenance=ProvenanceRecord(
                    extractor_id="test",
                    extractor_version="1.0",
                    sample_count=1,
                ),
            )

            with self.assertRaises(ValueError) as ctx:
                profile.validate()
            self.assertIn("consent is not active", str(ctx.exception))
