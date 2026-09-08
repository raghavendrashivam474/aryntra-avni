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


# ============================================================
# V2.5: Voice Conversion Request
# ============================================================
# Sibling to VoiceRequest. Used for speech-to-speech conversion.
# See ADR-0012 for rationale.

@dataclass
class VoiceConversionRequest:
    """Request to convert source speech into a target voice identity."""
    target_identity_id: str
    source_audio_bytes: bytes
    source_audio_format: str = "wav"
    source_sample_rate: int = 16000
    context: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

    def validate(self) -> None:
        """Validate the conversion request."""
        if not self.target_identity_id or not self.target_identity_id.strip():
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="target_identity_id must be a non-empty string.",
            )
        if not self.source_audio_bytes or len(self.source_audio_bytes) < 100:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="source_audio_bytes must contain valid audio data (minimum 100 bytes).",
            )
        if self.source_sample_rate < 8000 or self.source_sample_rate > 48000:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message=f"source_sample_rate must be between 8000 and 48000, got {self.source_sample_rate}.",
            )
