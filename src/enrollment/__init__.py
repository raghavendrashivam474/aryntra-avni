"""Voice Enrollment package for Avni V1.

Provides the pipeline for enrolling authorized voice recordings
into reusable Voice Identity representations.
"""

from src.enrollment.contracts import (
    AudioSample,
    EnrollmentRequest,
    EnrollmentResult,
    EnrollmentStatus,
)
from src.enrollment.audio_validator import validate_audio_file, validate_enrollment_audio
from src.enrollment.preprocessor import preprocess_audio
from src.enrollment.enrollment_service import EnrollmentService

__all__ = [
    "AudioSample",
    "EnrollmentRequest",
    "EnrollmentResult",
    "EnrollmentStatus",
    "EnrollmentService",
    "validate_audio_file",
    "validate_enrollment_audio",
    "preprocess_audio",
]
