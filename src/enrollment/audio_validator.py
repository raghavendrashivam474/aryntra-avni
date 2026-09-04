"""Audio validation for enrollment recordings.

Validates that supplied audio files meet minimum requirements
for voice representation extraction.
"""

import logging
import struct
import wave
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Minimum requirements for enrollment audio
MIN_DURATION_SECONDS = 1.0
MAX_DURATION_SECONDS = 60.0
MIN_SAMPLE_RATE = 16000
SUPPORTED_FORMATS = {".wav"}


class AudioValidationError(Exception):
    """Raised when audio fails validation."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.details = details or {}


def validate_audio_file(file_path: Path) -> Tuple[bool, List[str]]:
    """Validate a single audio file for enrollment suitability.

    Returns:
        (is_valid, list_of_error_messages)
    """
    errors = []
    path = Path(file_path)

    # 1. File existence
    if not path.is_file():
        return False, [f"File not found: {path}"]

    # 2. Format check
    if path.suffix.lower() not in SUPPORTED_FORMATS:
        errors.append(
            f"Unsupported format '{path.suffix}'. "
            f"Supported: {SUPPORTED_FORMATS}"
        )

    # 3. File size sanity
    file_size = path.stat().st_size
    if file_size < 1000:
        errors.append(f"File too small ({file_size} bytes), likely corrupt")
    if file_size > 50 * 1024 * 1024:
        errors.append(f"File too large ({file_size} bytes), max 50MB")

    # 4. WAV header validation
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                frame_rate = wf.getframerate()
                n_frames = wf.getnframes()
                duration = n_frames / frame_rate if frame_rate > 0 else 0

                if frame_rate < MIN_SAMPLE_RATE:
                    errors.append(
                        f"Sample rate {frame_rate}Hz below minimum "
                        f"{MIN_SAMPLE_RATE}Hz"
                    )
                if duration < MIN_DURATION_SECONDS:
                    errors.append(
                        f"Duration {duration:.2f}s below minimum "
                        f"{MIN_DURATION_SECONDS}s"
                    )
                if duration > MAX_DURATION_SECONDS:
                    errors.append(
                        f"Duration {duration:.2f}s exceeds maximum "
                        f"{MAX_DURATION_SECONDS}s"
                    )
                if channels > 2:
                    errors.append(
                        f"Too many channels ({channels}), max 2"
                    )

                logger.debug(
                    "Audio validated | file=%s rate=%d channels=%d "
                    "duration=%.2fs",
                    path.name, frame_rate, channels, duration,
                )

        except wave.Error as e:
            errors.append(f"Invalid WAV file: {e}")
        except Exception as e:
            errors.append(f"Cannot read audio file: {e}")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_enrollment_audio(file_paths: List[Path]) -> Tuple[bool, dict]:
    """Validate a batch of audio files for enrollment.

    Returns:
        (all_valid, {str(path): [errors]})
    """
    results = {}
    all_valid = True

    for path in file_paths:
        is_valid, errors = validate_audio_file(path)
        results[str(path)] = errors
        if not is_valid:
            all_valid = False

    return all_valid, results
