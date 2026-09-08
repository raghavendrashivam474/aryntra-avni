"""Integration tests verifying the VoiceCapability.convert() orchestrator routing and fallbacks."""

import pytest
from src.contracts.voice import VoiceIdentity, VoiceConversionRequest
from src.contracts.errors import AvniVoiceError
from src.contracts.renderer import RenderResult, VoiceConverter
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, ConverterRegistry
from tests.adapters.voice_conversion.test_converters import create_mock_wav_bytes, create_mock_embedding_bytes


class MockBrokenNeuralConverter(VoiceConverter):
    """Simulates a neural converter that fails, forcing a fallback."""
    @property
    def converter_id(self) -> str:
        return "speecht5_vc"

    def is_available(self) -> bool:
        return True

    def convert(self, source_audio_bytes, voice_config, context=None):
        raise RuntimeError("Neural inference pipeline crashed unexpectedly (simulated).")


class MockWorkingNeuralConverter(VoiceConverter):
    """Simulates a highly functional neural converter."""
    @property
    def converter_id(self) -> str:
        return "speecht5_vc"

    def is_available(self) -> bool:
        return True

    def convert(self, source_audio_bytes, voice_config, context=None):
        return RenderResult(
            audio_bytes=source_audio_bytes,
            audio_format="wav",
            sample_rate=16000,
            duration_seconds=1.5,
            metadata={"engine": "speecht5_vc_mocked"}
        )


class DummyAcousticConverter(VoiceConverter):
    """Simulates our fast, deterministic acoustic conversion fallback."""
    @property
    def converter_id(self) -> str:
        return "acoustic_vc"

    def is_available(self) -> bool:
        return True

    def convert(self, source_audio_bytes, voice_config, context=None):
        return RenderResult(
            audio_bytes=source_audio_bytes,
            audio_format="wav",
            sample_rate=16000,
            duration_seconds=1.5,
            metadata={"engine": "acoustic_vc_mocked"}
        )


def test_capability_routing_to_neural_converter():
    identities = IdentityRegistry()
    converters = ConverterRegistry()
    
    # 1. Register working mock neural converter
    converters.register(MockWorkingNeuralConverter())
    
    # 2. Register neural xvector identity
    target_rep = create_mock_embedding_bytes(dim=512)
    identity = VoiceIdentity(
        identity_id="target-neural-voice",
        renderer_id="speecht5",  # neural routing flag
        voice_configuration={"representation_data": target_rep},
        provenance={}
    )
    identities.register(identity)
    
    capability = VoiceCapability(identity_registry=identities, converter_registry=converters)
    
    source_audio = create_mock_wav_bytes(duration_sec=1.5, sample_rate=16000)
    request = VoiceConversionRequest(
        target_identity_id="target-neural-voice",
        source_audio_bytes=source_audio,
        source_sample_rate=16000
    )
    
    response = capability.convert(request)
    
    assert response.audio_bytes == source_audio
    assert response.metadata["converter_id"] == "speecht5_vc"
    assert response.metadata["fallback_used"] is False
    assert response.metadata["engine"] == "speecht5_vc_mocked"


def test_capability_fallback_triggers_when_neural_fails():
    identities = IdentityRegistry()
    converters = ConverterRegistry()
    
    # Register broken neural and working acoustic converters
    converters.register(MockBrokenNeuralConverter())
    converters.register(DummyAcousticConverter())
    
    target_rep = create_mock_embedding_bytes(dim=512)
    identity = VoiceIdentity(
        identity_id="target-neural-voice",
        renderer_id="speecht5",
        voice_configuration={"representation_data": target_rep},
        provenance={}
    )
    identities.register(identity)
    
    capability = VoiceCapability(identity_registry=identities, converter_registry=converters)
    
    source_audio = create_mock_wav_bytes(duration_sec=1.5, sample_rate=16000)
    request = VoiceConversionRequest(
        target_identity_id="target-neural-voice",
        source_audio_bytes=source_audio
    )
    
    response = capability.convert(request)
    
    # Verify fallback completed successfully
    assert response.metadata["converter_id"] == "acoustic_vc"
    assert response.metadata["primary_converter_id"] == "speecht5_vc"
    assert response.metadata["fallback_used"] is True
    assert response.metadata["engine"] == "acoustic_vc_mocked"


def test_capability_routing_for_non_neural_target_routes_directly_to_acoustic():
    identities = IdentityRegistry()
    converters = ConverterRegistry()
    
    converters.register(DummyAcousticConverter())
    
    # Identity targeting piper (offline non-neural converter mapping)
    identity = VoiceIdentity(
        identity_id="target-piper-voice",
        renderer_id="piper",
        voice_configuration={},
        provenance={}
    )
    identities.register(identity)
    
    capability = VoiceCapability(identity_registry=identities, converter_registry=converters)
    
    source_audio = create_mock_wav_bytes(duration_sec=1.5, sample_rate=16000)
    request = VoiceConversionRequest(
        target_identity_id="target-piper-voice",
        source_audio_bytes=source_audio
    )
    
    response = capability.convert(request)
    
    assert response.metadata["converter_id"] == "acoustic_vc"
    assert response.metadata["fallback_used"] is False
    assert response.metadata["engine"] == "acoustic_vc_mocked"


def test_capability_unknown_target_raises():
    capability = VoiceCapability()
    source_audio = create_mock_wav_bytes(duration_sec=0.5, sample_rate=16000)
    
    request = VoiceConversionRequest(
        target_identity_id="nonexistent-target",
        source_audio_bytes=source_audio
    )
    
    with pytest.raises(AvniVoiceError) as exc_info:
        capability.convert(request)
    assert "is not registered or found" in exc_info.value.message
