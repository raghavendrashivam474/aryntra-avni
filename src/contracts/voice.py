"""Voice Request, Response, and Identity contracts.

These are the public data structures that NAV and any other consumer
interacts with. They must remain stable across renderer changes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class VoiceRequest:
    """Inbound request for speech synthesis."""

    text: str
    identity_id: str
    request_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    streaming: bool = False

    def validate(self) -> None:
        """Raises AvniVoiceError(INVALID_REQUEST) if invariants are violated."""
        from src.contracts.errors import AvniVoiceError, VoiceErrorCode

        if not isinstance(self.text, str) or not self.text.strip():
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="text must be a non-empty string.",
                details={"field": "text", "value": repr(self.text)},
            )
        if not isinstance(self.identity_id, str) or not self.identity_id.strip():
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="identity_id must be a non-empty string.",
                details={"field": "identity_id", "value": repr(self.identity_id)},
            )


@dataclass(frozen=True)
class VoiceResponse:
    """Outbound response containing generated audio."""

    audio_bytes: bytes
    audio_format: str          # e.g. "wav", "pcm", "mp3"
    sample_rate: int
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None


@dataclass(frozen=True)
class VoiceIdentity:
    """Stable representation of a voice identity.

    Independent of any specific TTS engine. The renderer_id links
    this identity to a registered TTSRenderer adapter.
    """

    identity_id: str
    renderer_id: str
    voice_configuration: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Dict[str, Any]] = None
    fallback_renderer_id: Optional[str] = None
    fallback_voice_configuration: Dict[str, Any] = field(default_factory=dict)
    representation_id: Optional[str] = None
    profile_id: Optional[str] = None
