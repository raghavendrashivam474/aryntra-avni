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