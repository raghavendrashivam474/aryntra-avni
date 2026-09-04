"""Audio preprocessing for enrollment.

Normalizes audio recordings to a consistent format suitable
for voice representation extraction.
"""

import io
import logging
import struct
import wave
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1
TARGET_SAMPLE_WIDTH = 2


def load_wav_audio(file_path: Path) -> Tuple[bytes, int, int, int]:
    """Load a WAV file and return (raw_frames, sample_rate, channels, sample_width)."""
    with wave.open(str(file_path), "rb") as wf:
        return (
            wf.readframes(wf.getnframes()),
            wf.getframerate(),
            wf.getnchannels(),
            wf.getsampwidth(),
        )


def preprocess_audio(
    file_path: Path,
    target_rate: int = TARGET_SAMPLE_RATE,
    target_channels: int = TARGET_CHANNELS,
) -> bytes:
    """Preprocess an audio file to a normalized WAV byte stream."""
    frames, rate, channels, width = load_wav_audio(file_path)

    logger.debug(
        "Preprocessing | file=%s rate=%d channels=%d width=%d frames=%d",
        file_path.name, rate, channels, width, len(frames),
    )

    if rate == target_rate and channels == target_channels and width == TARGET_SAMPLE_WIDTH:
        logger.debug("Audio already matches target format")
        with open(file_path, "rb") as f:
            return f.read()

    if channels != target_channels and channels == 2:
        logger.info("Converting stereo to mono for %s", file_path.name)
        frames = _stereo_to_mono(frames, width)
        channels = target_channels

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(width)
        wf.setframerate(rate)
        wf.writeframes(frames)

    return buf.getvalue()


def _stereo_to_mono(frames: bytes, sample_width: int) -> bytes:
    """Convert stereo PCM frames to mono by averaging channels."""
    if sample_width == 2:
        n_samples = len(frames) // 2
        samples = struct.unpack(f"<{n_samples}h", frames)
        mono = []
        for i in range(0, n_samples, 2):
            left = samples[i]
            right = samples[i + 1] if i + 1 < n_samples else left
            mono.append((left + right) // 2)
        return struct.pack(f"<{len(mono)}h", *mono)

    logger.warning("Stereo-to-mono not implemented for %d-byte samples", sample_width)
    return frames
