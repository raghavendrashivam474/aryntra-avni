"""Local filesystem storage for Voice Identity Profiles."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union

from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.profiles.voice_profile import VoiceIdentityProfile

logger = logging.getLogger(__name__)


class ProfileStore:
    """Manages persistent storage and retrieval of VoiceIdentityProfiles.

    Uses local filesystem JSON serialization. Atomic file replacement
    is employed during writes to prevent corruption.
    """

    def __init__(self, storage_dir: Union[str, Path]):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_path(self, identity_id: str) -> Path:
        sanitized = "".join(c for c in identity_id if c.isalnum() or c in ("-", "_")).strip()
        if not sanitized:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message=f"Invalid identity_id: '{identity_id}'",
            )
        return self.storage_dir / f"{sanitized}.json"

    def save(self, profile: VoiceIdentityProfile) -> Path:
        """Persist a VoiceIdentityProfile to disk atomically."""
        profile.validate()
        target_path = self._get_path(profile.identity_id)
        temp_path = target_path.with_suffix(".tmp")

        try:
            payload = profile.to_dict()
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            temp_path.replace(target_path)
            logger.info("Persisted voice profile '%s' to %s", profile.identity_id, target_path)
            return target_path
        except Exception as exc:
            if temp_path.exists():
                temp_path.unlink()
            logger.error("Failed to persist profile '%s': %s", profile.identity_id, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Failed to persist voice profile '{profile.identity_id}': {exc}",
                cause=exc,
            ) from exc

    def load(self, identity_id: str) -> VoiceIdentityProfile:
        """Load and validate a VoiceIdentityProfile by identity_id."""
        path = self._get_path(identity_id)
        if not path.is_file():
            raise AvniVoiceError(
                code=VoiceErrorCode.UNKNOWN_IDENTITY,
                message=f"Voice profile '{identity_id}' not found at {path}",
                details={"identity_id": identity_id, "path": str(path)},
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            profile = VoiceIdentityProfile.from_dict(data)
            profile.validate()
            return profile
        except AvniVoiceError:
            raise
        except Exception as exc:
            logger.error("Failed to load or validate profile from %s: %s", path, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Corrupted or invalid voice profile at '{path}': {exc}",
                details={"path": str(path)},
                cause=exc,
            ) from exc

    def exists(self, identity_id: str) -> bool:
        """Check whether a profile exists."""
        try:
            return self._get_path(identity_id).is_file()
        except Exception:
            return False

    def list_identities(self) -> List[str]:
        """List all available profile identity IDs."""
        identities = []
        for file in sorted(self.storage_dir.glob("*.json")):
            identities.append(file.stem)
        return identities

    def delete(self, identity_id: str) -> bool:
        """Delete a profile from storage."""
        path = self._get_path(identity_id)
        if path.is_file():
            path.unlink()
            logger.info("Deleted voice profile '%s'", identity_id)
            return True
        return False
