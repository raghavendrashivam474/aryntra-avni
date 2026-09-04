"""Domain error definitions for Avni Voice capability."""

from enum import Enum
from typing import Optional, Union


class VoiceErrorCode(str, Enum):
    INVALID_REQUEST = "INVALID_REQUEST"
    UNKNOWN_IDENTITY = "UNKNOWN_IDENTITY"
    RENDERER_UNAVAILABLE = "RENDERER_UNAVAILABLE"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    CONFIGURATION_FAILURE = "CONFIGURATION_FAILURE"
    TIMEOUT = "TIMEOUT"


class AvniVoiceError(Exception):
    """Base exception for all Avni Voice domain errors.

    Raw implementation exceptions must never leak through the public API.
    All failures are wrapped in this type with a structured error code.
    """

    def __init__(
        self,
        code: Union[VoiceErrorCode, str],
        message: str,
        details: Optional[dict] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.cause = cause

    @property
    def code_str(self) -> str:
        return self.code.value if hasattr(self.code, "value") else str(self.code)

    def to_dict(self) -> dict:
        return {
            "error_code": self.code_str,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"AvniVoiceError(code={self.code_str!r}, message={self.message!r})"

    def __str__(self) -> str:
        return f"[{self.code_str}] {self.message}"