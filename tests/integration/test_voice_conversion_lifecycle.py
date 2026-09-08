"""End-to-end Voice Conversion lifecycle and persistent identity verification tests."""

import tempfile
from pathlib import Path
import pytest

from src.contracts.voice import VoiceConversionRequest
from src.contracts.errors import AvniVoiceError
from src.representation.neural_extractor import NeuralSpeakerExtractor
from src.profiles.voice_profile import VoiceIdentityProfile
from src.profiles.consent import ConsentRecord, ProvenanceRecord, ConsentStatus
from src.profiles.profile_store import ProfileStore
from src.enrollment.contracts import AudioSample, EnrollmentRequest
from src.enrollment.enrollment_service import EnrollmentService
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, ConverterRegistry
from src.adapters.voice_conversion.acoustic_vc_adapter import AcousticVCAdapter
from tests.adapters.voice_conversion.test_converters import create_mock_wav_bytes


def test_end_to_end_enroll_persist_reload_convert_lifecycle():
    """Verify that a persistent target identity remains functional across process boundaries."""
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        storage_path = Path(tmp_dir)
        
        # ---------------------------------------------------------
        # PHASE 1: Generate reference enrollment samples and enroll
        # ---------------------------------------------------------
        sample_1_path = storage_path / "enroll_ref1.wav"
        sample_2_path = storage_path / "enroll_ref2.wav"
        
        sample_1_path.write_bytes(create_mock_wav_bytes(duration_sec=1.5, sample_rate=16000))
        sample_2_path.write_bytes(create_mock_wav_bytes(duration_sec=1.5, sample_rate=16000))
        
        samples = [
            AudioSample(file_path=sample_1_path, source_id="authorized-speaker-a"),
            AudioSample(file_path=sample_2_path, source_id="authorized-speaker-a"),
        ]
        
        enroll_request = EnrollmentRequest(
            identity_id="persistent-voice-a",
            samples=samples,
            provenance={"enrolled_by": "V2.5 integration test"}
        )
        
        extractor = NeuralSpeakerExtractor()
        enroll_service = EnrollmentService(representation_extractor=extractor)
        
        enroll_result = enroll_service.enroll(enroll_request)
        assert enroll_result.is_success is True
        assert enroll_result.representation_data is not None
        assert len(enroll_result.representation_data) == 2048  # 512 floats * 4 bytes
        
        # ---------------------------------------------------------
        # PHASE 2: Create profile record and save atomically to disk
        # ---------------------------------------------------------
        from src.representation.base import VoiceRepresentation
        
        rep = VoiceRepresentation(
            representation_id="neural_xvector_persistent-voice-a",
            version=enroll_result.representation_version,
            data=enroll_result.representation_data,
            metadata=enroll_result.metadata.get("representation", {})
        )
        
        consent = ConsentRecord(
            source_id="authorized-speaker-a",
            status=ConsentStatus.ACTIVE,
            scope="voice_synthesis_and_conversion"
        )
        
        provenance = ProvenanceRecord(
            extractor_id=extractor.extractor_id,
            extractor_version=extractor.version,
            sample_count=2,
            source_sample_hashes=["hash1", "hash2"]
        )
        
        profile = VoiceIdentityProfile(
            identity_id="persistent-voice-a",
            representation=rep,
            consent=consent,
            provenance=provenance
        )
        
        profile_store = ProfileStore(storage_dir=storage_path)
        profile_store.save(profile)
        assert profile_store.exists("persistent-voice-a") is True
        
        # ---------------------------------------------------------
        # PHASE 3: Clear memory space (Simulate clean system restart)
        # ---------------------------------------------------------
        del extractor
        del enroll_service
        del profile
        
        reloaded_store = ProfileStore(storage_dir=storage_path)
        fresh_identities = IdentityRegistry()
        fresh_converters = ConverterRegistry()
        
        # Register the deterministic acoustic morphing converter
        acoustic_converter = AcousticVCAdapter()
        fresh_converters.register(acoustic_converter)
        
        capability = VoiceCapability(
            identity_registry=fresh_identities,
            converter_registry=fresh_converters,
            profile_store=reloaded_store
        )
        
        # In-memory registry is fresh and has not resolved this identity yet
        assert fresh_identities.exists("persistent-voice-a") is False
        
        # ---------------------------------------------------------
        # PHASE 4: Request Conversion (Verifying on-demand disk resolution)
        # ---------------------------------------------------------
        source_audio = create_mock_wav_bytes(duration_sec=1.0, sample_rate=16000)
        request = VoiceConversionRequest(
            target_identity_id="persistent-voice-a",
            source_audio_bytes=source_audio,
            source_sample_rate=16000
        )
        
        response = capability.convert(request)
        
        # ---------------------------------------------------------
        # PHASE 5: Verify results and identity persistence invariants
        # ---------------------------------------------------------
        assert response.audio_bytes is not None
        assert response.audio_format == "wav"
        assert response.sample_rate == 16000
        assert response.metadata["identity_id"] == "persistent-voice-a"
        assert response.metadata["converter_id"] == "acoustic_vc"
        assert response.metadata["representation_id"] == "neural_xvector_persistent-voice-a"
        assert response.metadata["profile_id"] == "persistent-voice-a"
        
        # Verify in-memory registry now caches the resolved identity
        assert fresh_identities.exists("persistent-voice-a") is True
