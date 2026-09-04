"""Consent and Provenance contracts for Voice Identity Profiles."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ConsentStatus(str, Enum):
    """Current authorization state of a voice identity."""
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


@dataclass(frozen=True)
class ConsentRecord:
    """Formal record of voice usage authorization."""
    source_id: str
    status: ConsentStatus = ConsentStatus.ACTIVE
    scope: str = "voice_identity_enrollment"
    granted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    revoked_at: Optional[str] = None
    terms_version: str = "1.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        """True if consent is currently active and valid."""
        return self.status == ConsentStatus.ACTIVE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "status": self.status.value,
            "scope": self.scope,
            "granted_at": self.granted_at,
            "revoked_at": self.revoked_at,
            "terms_version": self.terms_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsentRecord":
        return cls(
            source_id=data["source_id"],
            status=ConsentStatus(data.get("status", ConsentStatus.ACTIVE.value)),
            scope=data.get("scope", "voice_identity_enrollment"),
            granted_at=data.get("granted_at", datetime.now(timezone.utc).isoformat()),
            revoked_at=data.get("revoked_at"),
            terms_version=data.get("terms_version", "1.0"),
            metadata=data.get("metadata", {}),
        )


@dataclass(frozen=True)
class ProvenanceRecord:
    """Traceability metadata recording how a voice identity was derived."""
    extractor_id: str
    extractor_version: str
    sample_count: int
    source_sample_hashes: List[str] = field(default_factory=list)
    enrolled_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    environment_info: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "extractor_id": self.extractor_id,
            "extractor_version": self.extractor_version,
            "sample_count": self.sample_count,
            "source_sample_hashes": self.source_sample_hashes,
            "enrolled_at": self.enrolled_at,
            "environment_info": self.environment_info,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceRecord":
        return cls(
            extractor_id=data["extractor_id"],
            extractor_version=data["extractor_version"],
            sample_count=data.get("sample_count", 0),
            source_sample_hashes=data.get("source_sample_hashes", []),
            enrolled_at=data.get("enrolled_at", datetime.now(timezone.utc).isoformat()),
            environment_info=data.get("environment_info", {}),
        )
