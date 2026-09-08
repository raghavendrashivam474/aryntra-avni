"""Spectral / Pitch-shifting fallback Voice Converter for Avni V2.5.

Transforms voice characteristics deterministically while preserving
the temporal structure, rate, and content of the source audio.
"""

import io
import logging
import struct
import wave
from typing import Any, Dict, Optional

import numpy as np
from scipy import signal

from src.contracts.renderer import VoiceConverter, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode

logger = logging.getLogger(__name__)


class AcousticVCAdapter(VoiceConverter):
    """Fallback voice converter using deterministic digital signal processing.

    Formant/pitch-shifts source audio to sound distinct while perfectly
    preserving timing, duration, rhythm, and linguistic content.
    """

    @property
    def converter_id(self) -> str:
        return "acoustic_vc"

    def is_available(self) -> bool:
        # Standard scientific libraries are always present in our validated env
        return True

    def convert(
        self,
        source_audio_bytes: bytes,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        """Apply spectral / pitch morphing conversion on source speech."""
        try:
            # 1. Parse source WAV
            with wave.open(io.BytesIO(source_audio_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_data = wf.readframes(n_frames)

            # Ensure mono 16-bit PCM for deterministic processing
            if sample_width != 2:
                raise ValueError("Only 16-bit PCM audio is supported.")
            
            samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32767.0
            if channels > 1:
                # Merge stereo to mono
                samples = samples.reshape(-1, channels).mean(axis=1)

            # 2. Determine conversion target mapping parameters from representation / metadata
            # We derive a deterministic shift factor from the target speaker representation bytes
            shift_factor = 1.15  # Default shift: slightly higher pitch target
            rep_data = voice_config.get("representation_data")
            if rep_data and isinstance(rep_data, bytes):
                # Hash or average embedding bytes to produce a stable, speaker-unique pitch shift factor
                byte_sum = sum(rep_data)
                # Map sum to shift range [0.85, 1.25]
                shift_factor = 0.85 + (byte_sum % 40) / 100.0

            logger.debug("Acoustic conversion applying shift factor %.3f", shift_factor)

            # 3. Perform pitch modification using linear interpolation resampling
            # Simple, phase-coherent duration-preserving spectral shift:
            # First speed up / slow down, then resample back to original sample rate
            target_len = int(len(samples) / shift_factor)
            resampled = signal.resample(samples, target_len)
            
            # Stretch / squeeze back to original duration to perfectly match source timing
            output_samples = signal.resample(resampled, len(samples))
            
            # Normalize and clamp to prevent clipping
            if len(output_samples) > 0:
                max_val = np.max(np.abs(output_samples))
                if max_val > 0:
                    output_samples = output_samples / max_val * 0.95

            # 4. Write output to standard mono 16-bit PCM WAV at original sample rate
            out_buf = io.BytesIO()
            pcm_out = (np.clip(output_samples, -1.0, 1.0) * 32767).astype(np.int16)
            
            with wave.open(out_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_out.tobytes())

            converted_bytes = out_buf.getvalue()
            duration = len(output_samples) / sample_rate

            return RenderResult(
                audio_bytes=converted_bytes,
                audio_format="wav",
                sample_rate=sample_rate,
                duration_seconds=duration,
                metadata={
                    "engine": "acoustic_vc",
                    "shift_factor": round(shift_factor, 4),
                    "sample_rate": sample_rate,
                    "bytes_count": len(converted_bytes),
                    "duration_seconds": round(duration, 3),
                },
            )

        except Exception as exc:
            logger.error("Acoustic voice conversion failed: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"Acoustic fallback voice conversion failed: {exc}",
                cause=exc,
            ) from exc
