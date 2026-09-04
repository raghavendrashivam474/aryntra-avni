"""In-memory registries for voice identities and TTS renderers."""

from typing import Dict
from src.contracts.voice import VoiceIdentity
from src.contracts.renderer import TTSRenderer
from src.contracts.errors import AvniVoiceError, VoiceErrorCode


class IdentityRegistry:
    """Stores and retrieves VoiceIdentity objects by identity_id."""

    def __init__(self) -> None:
        self._identities: Dict[str, VoiceIdentity] = {}

    def register(self, identity: VoiceIdentity) -> None:
        self._identities[identity.identity_id] = identity

    def get(self, identity_id: str) -> VoiceIdentity:
        if identity_id not in self._identities:
            raise AvniVoiceError(
                code=VoiceErrorCode.UNKNOWN_IDENTITY,
                message=f"Voice identity '{identity_id}' is not registered.",
                details={"identity_id": identity_id},
            )
        return self._identities[identity_id]

    def exists(self, identity_id: str) -> bool:
        return identity_id in self._identities


class RendererRegistry:
    """Stores and retrieves TTSRenderer adapters by renderer_id."""

    def __init__(self) -> None:
        self._renderers: Dict[str, TTSRenderer] = {}

    def register(self, renderer: TTSRenderer) -> None:
        self._renderers[renderer.renderer_id] = renderer

    def get(self, renderer_id: str) -> TTSRenderer:
        if renderer_id not in self._renderers:
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message=f"Renderer '{renderer_id}' is not registered.",
                details={"renderer_id": renderer_id},
            )
        renderer = self._renderers[renderer_id]
        if not renderer.is_available():
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message=f"Renderer '{renderer_id}' is registered but currently unavailable.",
                details={"renderer_id": renderer_id},
            )
        return renderer