"""Voice Representation abstraction for Avni V1.

The kernel knows concepts. Plugins know technologies.

VoiceRepresentation is the abstract boundary. Concrete implementations
(acoustic features, neural embeddings, etc.) live behind this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class VoiceRepresentation:
    """A reusable, renderer-independent voice identity representation.

    This is the architectural primitive that V1 establishes.
    The actual data format is implementation-specific and hidden
    behind the RepresentationExtractor interface.
    """
    representation_id: str
    version: str
    data: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_valid(self) -> bool:
        """Basic structural validity check."""
        return (
            bool(self.representation_id)
            and bool(self.version)
            and len(self.data) > 0
        )


class RepresentationExtractor(ABC):
    """Abstract interface for extracting voice representations from audio.

    Implementations may use:
    - Acoustic feature statistics
    - Neural speaker embeddings (d-vectors, x-vectors)
    - Model-specific conditioning parameters
    - Any future representation technology

    The kernel depends on this ABC. Concrete extractors are plugins.
    """

    @property
    @abstractmethod
    def extractor_id(self) -> str:
        """Unique identifier for this extractor (e.g., 'acoustic_stats_v1')."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Version of the representation format this extractor produces."""
        ...

    @abstractmethod
    def extract(
        self,
        audio_samples: List[bytes],
    ) -> VoiceRepresentation:
        """Extract a voice representation from preprocessed audio samples.

        Args:
            audio_samples: List of preprocessed WAV byte streams.

        Returns:
            A VoiceRepresentation containing the extracted identity data.

        Raises:
            ExtractionError: If extraction fails.
        """
        ...

    @abstractmethod
    def similarity(
        self,
        rep_a: VoiceRepresentation,
        rep_b: VoiceRepresentation,
    ) -> float:
        """Compute similarity between two representations.

        Returns:
            A float in [0.0, 1.0] where 1.0 = identical.
        """
        ...


class ExtractionError(Exception):
    """Raised when representation extraction fails."""
    def __init__(self, message: str, details: Optional[dict] = None):
        super().__init__(message)
        self.details = details or {}
