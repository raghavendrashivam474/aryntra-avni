"""Renderer interface contract.

Every TTS engine adapter must implement TTSRenderer.
The rest of Avni never imports a concrete adapter directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RenderResult:
    """Raw output from a concrete TTS adapter."""

    audio_bytes: bytes
    audio_format: str
    sample_rate: int
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TTSRenderer(ABC):
    """Abstract contract for all speech-synthesis backends."""

    @property
    @abstractmethod
    def renderer_id(self) -> str:
        """Unique identifier for this renderer (e.g. 'piper', 'elevenlabs')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying engine is ready to synthesize."""
        ...

    @abstractmethod
    def render(
        self,
        text: str,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        """Synthesize *text* into audio.

        Args:
            text: The text to speak.
            voice_config: Identity-specific parameters forwarded from VoiceIdentity.
            context: Optional request-level context hints.

        Returns:
            A RenderResult containing raw audio bytes and metadata.

        Raises:
            AvniVoiceError: On any generation or configuration failure.
        """
        ...

# ============================================================
# V2.5: Voice Conversion Abstraction
# ============================================================
# Sibling to TTSRenderer. Shares RenderResult as output type.
# See ADR-0012 for rationale.

class VoiceConverter(ABC):
    """Abstract base for voice conversion adapters.

    Voice conversion transforms source speech to match a target
    voice identity while preserving linguistic content, timing,
    and prosodic structure.

    Unlike TTSRenderer (which takes text), VoiceConverter takes
    source audio as input.
    """

    @property
    @abstractmethod
    def converter_id(self) -> str:
        """Unique identifier for this voice converter implementation."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the converter's dependencies are satisfied."""
        ...

    @abstractmethod
    def convert(
        self,
        source_audio_bytes: bytes,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        """Convert source speech to match the target voice identity.

        Args:
            source_audio_bytes: Raw audio bytes of the source speech.
            voice_config: Target identity configuration including
                'representation_data' (target speaker embedding)
                and optionally 'reference_audio_bytes' (target
                reference clip for model conditioning).
            context: Optional runtime context.

        Returns:
            RenderResult with converted audio.
        """
        ...
