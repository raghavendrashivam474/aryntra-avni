"""Tests for S3 Voice Identity Profile Persistence and Consent."""

import tempfile
from pathlib import Path
from unittest import TestCase

from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.representation.base import VoiceRepresentation
from src.profiles.consent import ConsentRecord, ConsentStatus, ProvenanceRecord
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.profile_store import ProfileStore


def _sample_profile(identity_id: str = "test_speaker_01", consent_active: bool = True) -> VoiceIdentityProfile:
    rep = VoiceRepresentation(
        representation_id="acoustic_stats_v1.0",
        version="1.0",
        data=b"\x01\x02\x03\x04" * 10,
        metadata={"dim": 5},
    )
    consent = ConsentRecord(
        source_id="user_john_doe",
        status=ConsentStatus.ACTIVE if consent_active else ConsentStatus.REVOKED,
        scope="voice_identity_enrollment",
    )
    provenance = ProvenanceRecord(
        extractor_id="acoustic_stats",
        extractor_version="1.0",
        sample_count=3,
        source_sample_hashes=["hash1", "hash2", "hash3"],
    )
    return VoiceIdentityProfile(
        identity_id=identity_id,
        representation=rep,
        consent=consent,
        provenance=provenance,
    )


class TestVoiceIdentityProfileContracts(TestCase):
    """Test VoiceIdentityProfile and Consent validations."""

    def test_valid_profile_serialization_roundtrip(self):
        profile = _sample_profile()
        profile.validate()

        data = profile.to_dict()
        reconstructed = VoiceIdentityProfile.from_dict(data)

        self.assertEqual(profile.identity_id, reconstructed.identity_id)
        self.assertEqual(profile.representation.data, reconstructed.representation.data)
        self.assertEqual(profile.consent.source_id, reconstructed.consent.source_id)
        self.assertEqual(profile.provenance.sample_count, reconstructed.provenance.sample_count)

    def test_revoked_consent_fails_validation(self):
        profile = _sample_profile(consent_active=False)
        with self.assertRaises(ValueError) as ctx:
            profile.validate()
        self.assertIn("consent is not active", str(ctx.exception))

    def test_unsupported_schema_version_fails(self):
        data = _sample_profile().to_dict()
        data["schema_version"] = "999.0"
        with self.assertRaises(ValueError) as ctx:
            VoiceIdentityProfile.from_dict(data)
        self.assertIn("Unsupported profile schema version", str(ctx.exception))


class TestProfileStore(TestCase):
    """Test ProfileStore filesystem CRUD and error isolation."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store = ProfileStore(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_save_and_load_profile(self):
        profile = _sample_profile("alice_voice")
        path = self.store.save(profile)
        self.assertTrue(path.is_file())

        loaded = self.store.load("alice_voice")
        self.assertEqual(loaded.identity_id, "alice_voice")
        self.assertEqual(loaded.representation.data, profile.representation.data)
        self.assertTrue(self.store.exists("alice_voice"))

    def test_load_nonexistent_profile_raises_unknown_identity(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            self.store.load("ghost_identity")
        self.assertEqual(ctx.exception.code, VoiceErrorCode.UNKNOWN_IDENTITY)

    def test_load_corrupted_json_raises_configuration_failure(self):
        corrupt_file = Path(self.tmp_dir.name) / "corrupted.json"
        corrupt_file.write_text("{ incomplete json...", encoding="utf-8")

        with self.assertRaises(AvniVoiceError) as ctx:
            self.store.load("corrupted")
        self.assertEqual(ctx.exception.code, VoiceErrorCode.CONFIGURATION_FAILURE)

    def test_list_and_delete_identities(self):
        self.store.save(_sample_profile("voice_1"))
        self.store.save(_sample_profile("voice_2"))

        identities = self.store.list_identities()
        self.assertIn("voice_1", identities)
        self.assertIn("voice_2", identities)

        self.assertTrue(self.store.delete("voice_1"))
        self.assertFalse(self.store.exists("voice_1"))
        self.assertEqual(self.store.list_identities(), ["voice_2"])
