"""Enrollment contracts for V1 Voice Identity.

These define the data structures for enrolling a voice from
authorized recordings. Separate from the synthesis contracts
in src/contracts/voice.py.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class EnrollmentStatus(str, Enum):
    """Outcome of an enrollment attempt."""
    SUCCESS = "SUCCESS"
    INVALID_AUDIO = "INVALID_AUDIO"
    INSUFFICIENT_INPUT = "INSUFFICIENT_INPUT"
    EXTRACTION_FAILURE = "EXTRACTION_FAILURE"
    CONSENT_MISSING = "CONSENT_MISSING"


@dataclass(frozen=True)
class AudioSample:
    """A single authorized voice recording for enrollment."""
    file_path: Path
    source_id: str                          # who authorized this recording
    consent_granted: bool = True
    intended_use: str = "voice_identity_enrollment"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Returns a list of validation error strings. Empty = valid."""
        errors = []
        if not self.file_path.is_file():
            errors.append(f"Audio file not found: {self.file_path}")
        if not self.consent_granted:
            errors.append(f"Consent not granted for source '{self.source_id}'")
        if not self.source_id or not self.source_id.strip():
            errors.append("source_id must be a non-empty string")
        return errors


@dataclass(frozen=True)
class EnrollmentRequest:
    """Request to enroll a voice identity from authorized recordings."""
    identity_id: str
    samples: List[AudioSample]
    consent_metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Returns all validation errors across the request."""
        errors = []
        if not self.identity_id or not self.identity_id.strip():
            errors.append("identity_id must be a non-empty string")
        if len(self.samples) < 2:
            errors.append(
                f"Minimum 2 authorized recordings required, got {len(self.samples)}"
            )
        if len(self.samples) > 10:
            errors.append(
                f"Maximum 10 recordings for enrollment, got {len(self.samples)}"
            )
        for i, sample in enumerate(self.samples):
            sample_errors = sample.validate()
            for err in sample_errors:
                errors.append(f"Sample {i}: {err}")
        return errors


@dataclass(frozen=True)
class EnrollmentResult:
    """Outcome of a voice enrollment attempt."""
    status: EnrollmentStatus
    identity_id: str
    representation_data: Optional[bytes] = None
    representation_version: Optional[str] = None
    sample_count: int = 0
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_success(self) -> bool:
        return self.status == EnrollmentStatus.SUCCESS
