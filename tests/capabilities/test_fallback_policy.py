import pytest
from unittest.mock import MagicMock
from src.contracts.voice import VoiceRequest, VoiceIdentity
from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry


class DummyRenderer(TTSRenderer):
    def __init__(self, renderer_id: str, should_fail: bool = False, audio_bytes: bytes = b"RIFF....WAVE"):
        self._renderer_id = renderer_id
        self._should_fail = should_fail
        self._audio_bytes = audio_bytes

    @property
    def renderer_id(self) -> str:
        return self._renderer_id

    def is_available(self) -> bool:
        return True

    def render(self, text, voice_config, context=None):
        if self._should_fail:
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"{self._renderer_id} simulated failure",
            )
        return RenderResult(
            audio_bytes=self._audio_bytes,
            audio_format="wav",
            sample_rate=22050,
            metadata={"engine": self._renderer_id},
        )


def test_fallback_triggers_when_primary_fails():
    id_reg = IdentityRegistry()
    rend_reg = RendererRegistry()

    # Register failing primary and healthy fallback
    rend_reg.register(DummyRenderer("primary_cloud", should_fail=True))
    rend_reg.register(DummyRenderer("fallback_local", should_fail=False))

    id_reg.register(
        VoiceIdentity(
            identity_id="test_ident",
            renderer_id="primary_cloud",
            fallback_renderer_id="fallback_local",
        )
    )

    cap = VoiceCapability(identity_registry=id_reg, renderer_registry=rend_reg)
    resp = cap.synthesize(VoiceRequest(text="Hello", identity_id="test_ident"))

    assert resp.metadata["fallback_used"] is True
    assert resp.metadata["primary_renderer_id"] == "primary_cloud"
    assert resp.metadata["renderer_id"] == "fallback_local"
    assert resp.audio_bytes == b"RIFF....WAVE"


def test_double_failure_raises_structured_error():
    id_reg = IdentityRegistry()
    rend_reg = RendererRegistry()

    rend_reg.register(DummyRenderer("primary_cloud", should_fail=True))
    rend_reg.register(DummyRenderer("fallback_local", should_fail=True))

    id_reg.register(
        VoiceIdentity(
            identity_id="test_ident",
            renderer_id="primary_cloud",
            fallback_renderer_id="fallback_local",
        )
    )

    cap = VoiceCapability(identity_registry=id_reg, renderer_registry=rend_reg)
    with pytest.raises(AvniVoiceError) as exc_info:
        cap.synthesize(VoiceRequest(text="Hello", identity_id="test_ident"))

    assert exc_info.value.code == VoiceErrorCode.GENERATION_FAILURE
    assert "primary_cloud" in exc_info.value.message
    assert "fallback_local" in exc_info.value.message
    assert exc_info.value.details["primary_renderer_id"] == "primary_cloud"
    assert exc_info.value.details["fallback_renderer_id"] == "fallback_local"


def test_offline_identity_direct_synthesis():
    from src.capabilities.voice import create_default_voice_capability

    cap = create_default_voice_capability()
    resp = cap.synthesize(VoiceRequest(text="Local offline test.", identity_id="avni_offline"))

    assert resp.audio_format == "wav"
    assert resp.sample_rate == 22050
    assert resp.metadata["renderer_id"] == "piper"
    assert resp.metadata["fallback_used"] is False
    assert len(resp.audio_bytes) > 1000