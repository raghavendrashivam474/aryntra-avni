"""Voice Representation package for Avni V1.

Provides the abstraction layer for voice identity representations
and concrete extractor implementations.
"""

from src.representation.base import (
    ExtractionError,
    RepresentationExtractor,
    VoiceRepresentation,
)
from src.representation.acoustic_extractor import AcousticFeatureExtractor

__all__ = [
    "VoiceRepresentation",
    "RepresentationExtractor",
    "ExtractionError",
    "AcousticFeatureExtractor",
]
