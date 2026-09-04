"""Public voice capability package for Avni."""

from pathlib import Path
from typing import Optional

from src.contracts.voice import VoiceRequest, VoiceResponse, VoiceIdentity
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.contracts.renderer import TTSRenderer, RenderResult
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry
from src.capabilities.voice.identity_loader import IdentityLoader
from src.adapters.tts.edge_tts_adapter import EdgeTTSAdapter


def create_default_voice_capability(
    identities_dir: Optional[Path] = None,
) -> VoiceCapability:
    """Factory creating a ready-to-use VoiceCapability for NAV.

    Pre-registers default adapters (EdgeTTS) and loads all baseline identities
    from configs/identities/.
    """
    identity_reg = IdentityRegistry()
    renderer_reg = RendererRegistry()

    # Register default renderer adapter
    renderer_reg.register(EdgeTTSAdapter())

    # Load baseline identities
    config_path = identities_dir or (Path(__file__).resolve().parents[3] / "configs" / "identities")
    if config_path.is_dir():
        identities = IdentityLoader.load_directory(config_path)
        for ident in identities:
            identity_reg.register(ident)

    return VoiceCapability(
        identity_registry=identity_reg,
        renderer_registry=renderer_reg,
    )


__all__ = [
    "VoiceRequest",
    "VoiceResponse",
    "VoiceIdentity",
    "AvniVoiceError",
    "VoiceErrorCode",
    "TTSRenderer",
    "RenderResult",
    "VoiceCapability",
    "IdentityRegistry",
    "RendererRegistry",
    "IdentityLoader",
    "create_default_voice_capability",
]