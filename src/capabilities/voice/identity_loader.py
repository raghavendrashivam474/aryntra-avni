"""Identity Loader for Avni Voice configurations and profiles."""

import json
from pathlib import Path
from typing import Dict, List, Union, Optional

from src.contracts.voice import VoiceIdentity
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.profiles.voice_profile import VoiceIdentityProfile


class IdentityLoader:
    """Loads VoiceIdentity definitions from declarative files, directories, and profiles."""

    @staticmethod
    def load_from_dict(data: Dict) -> VoiceIdentity:
        """Parses a dictionary into a validated VoiceIdentity object."""
        if not isinstance(data, dict):
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Identity configuration data must be a dictionary.",
            )

        identity_id = data.get("identity_id")
        renderer_id = data.get("renderer_id")

        if not identity_id or not isinstance(identity_id, str):
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Identity configuration missing or invalid 'identity_id'.",
                details={"data": data},
            )

        if not renderer_id or not isinstance(renderer_id, str):
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Identity configuration missing or invalid 'renderer_id'.",
                details={"data": data},
            )

        return VoiceIdentity(
            identity_id=identity_id.strip(),
            renderer_id=renderer_id.strip(),
            voice_configuration=data.get("voice_configuration", {}),
            provenance=data.get("provenance", {}),
            fallback_renderer_id=data.get("fallback_renderer_id"),
            fallback_voice_configuration=data.get("fallback_voice_configuration", {}),
            representation_id=data.get("representation_id"),
            profile_id=data.get("profile_id"),
        )

    @staticmethod
    def load_from_profile(
        profile: VoiceIdentityProfile,
        default_renderer_id: str = "edge_tts",
        default_voice_config: Optional[Dict] = None,
        fallback_renderer_id: Optional[str] = "piper",
        fallback_voice_config: Optional[Dict] = None,
    ) -> VoiceIdentity:
        """Binds a persistent VoiceIdentityProfile to a synthesizable VoiceIdentity."""
        profile.validate()
        voice_cfg = default_voice_config or {}
        # Embed representation metadata into configuration for renderer context
        voice_cfg = dict(voice_cfg)
        voice_cfg["representation_id"] = profile.representation.representation_id
        voice_cfg["representation_version"] = profile.representation.version

        return VoiceIdentity(
            identity_id=profile.identity_id,
            renderer_id=default_renderer_id,
            voice_configuration=voice_cfg,
            provenance={
                "profile_schema_version": profile.schema_version,
                "consent_source_id": profile.consent.source_id,
                "provenance": profile.provenance.to_dict(),
            },
            fallback_renderer_id=fallback_renderer_id,
            fallback_voice_configuration=fallback_voice_config or {},
            representation_id=profile.representation.representation_id,
            profile_id=profile.identity_id,
        )

    @staticmethod
    def load_from_json_file(file_path: Union[str, Path]) -> VoiceIdentity:
        """Reads a JSON identity configuration file."""
        path = Path(file_path)
        if not path.is_file():
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Identity config file not found: {path}",
                details={"path": str(path)},
            )

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return IdentityLoader.load_from_dict(data)
        except json.JSONDecodeError as exc:
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Failed to parse identity JSON at '{path}': {str(exc)}",
                details={"path": str(path)},
                cause=exc,
            ) from exc

    @staticmethod
    def load_directory(dir_path: Union[str, Path]) -> List[VoiceIdentity]:
        """Loads all JSON identity profiles from a directory."""
        directory = Path(dir_path)
        if not directory.is_dir():
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Identities directory not found: {directory}",
                details={"directory": str(directory)},
            )

        identities = []
        for file in sorted(directory.glob("*.json")):
            identities.append(IdentityLoader.load_from_json_file(file))
        return identities
