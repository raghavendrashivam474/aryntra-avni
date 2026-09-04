"""Persistent Voice Identity Profile contract."""

import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.representation.base import VoiceRepresentation
from src.profiles.consent import ConsentRecord, ProvenanceRecord

PROFILE_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class VoiceIdentityProfile:
    """Complete, persistent entity representing an enrolled synthetic voice identity."""
    identity_id: str
    representation: VoiceRepresentation
    consent: ConsentRecord
    provenance: ProvenanceRecord
    schema_version: str = PROFILE_SCHEMA_VERSION
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Validate structural and consent invariants."""
        if not self.identity_id or not self.identity_id.strip():
            raise ValueError("identity_id must be a non-empty string.")
        if not self.representation or not self.representation.is_valid:
            raise ValueError("Profile contains an invalid VoiceRepresentation.")
        if not self.consent.is_usable:
            raise ValueError(f"Profile consent is not active (status={self.consent.status}).")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize profile to a dictionary with base64 encoded representation data."""
        return {
            "schema_version": self.schema_version,
            "identity_id": self.identity_id,
            "created_at": self.created_at,
            "representation": {
                "representation_id": self.representation.representation_id,
                "version": self.representation.version,
                "data_b64": base64.b64encode(self.representation.data).decode("ascii"),
                "metadata": self.representation.metadata,
            },
            "consent": self.consent.to_dict(),
            "provenance": self.provenance.to_dict(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VoiceIdentityProfile":
        """Deserialize profile from a dictionary."""
        schema_version = data.get("schema_version", "1.0")
        if schema_version != PROFILE_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported profile schema version: {schema_version} (expected {PROFILE_SCHEMA_VERSION})"
            )

        rep_dict = data["representation"]
        rep = VoiceRepresentation(
            representation_id=rep_dict["representation_id"],
            version=rep_dict["version"],
            data=base64.b64decode(rep_dict["data_b64"]),
            metadata=rep_dict.get("metadata", {}),
        )

        consent = ConsentRecord.from_dict(data["consent"])
        provenance = ProvenanceRecord.from_dict(data["provenance"])

        return cls(
            identity_id=data["identity_id"],
            representation=rep,
            consent=consent,
            provenance=provenance,
            schema_version=schema_version,
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            metadata=data.get("metadata", {}),
        )
