"""Identity Loader for Avni Voice configurations."""

import json
from pathlib import Path
from typing import Dict, List, Union
from src.contracts.voice import VoiceIdentity
from src.contracts.errors import AvniVoiceError, VoiceErrorCode


class IdentityLoader:
    """Loads VoiceIdentity definitions from files and directories."""

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