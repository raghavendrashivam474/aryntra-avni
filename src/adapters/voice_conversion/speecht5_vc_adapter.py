"""SpeechT5 Voice Conversion Adapter for Avni V2.5 / V3.0.

Provides neural speech-to-speech voice conversion using Microsoft's SpeechT5
Speech-to-Speech model conditioned on target identity speaker embeddings.
Supports V3.0 S2 request-time ExpressionConfig via context propagation.
"""

from __future__ import annotations

import io
import math
import logging
import struct
import wave
from typing import Any, Dict, List, Optional

from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.contracts.renderer import RenderResult, VoiceConverter

logger = logging.getLogger(__name__)


class SpeechT5VCAdapter(VoiceConverter):
    """Voice Converter adapter using Microsoft SpeechT5 Speech-to-Speech model.

    Takes source speech audio bytes, converts acoustic features while preserving
    linguistic content and timing, and projects timbre into the target speaker's
    voice embedding representation. Applies request-time expression controls
    (pitch, rate, energy) via context.
    """

    def __init__(
        self,
        model_name: str = "microsoft/speecht5_vc",
        vocoder_name: str = "microsoft/speecht5_hifigan",
        device: Optional[str] = None,
    ) -> None:
        self._model_name = model_name
        self._vocoder_name = vocoder_name
        self._device = device or "cpu"

        self._processor = None
        self._model = None
        self._vocoder = None
        self._initialized = False

    @property
    def converter_id(self) -> str:
        return "speecht5_vc"

    def is_available(self) -> bool:
        """Check if torch and transformers are available in runtime."""
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def _load_components(self) -> None:
        """Lazy load processor, model, and vocoder on first conversion request."""
        if self._initialized:
            return

        try:
            import torch
            from transformers import (
                SpeechT5ForSpeechToSpeech,
                SpeechT5HifiGan,
                SpeechT5Processor,
            )

            logger.info("Loading SpeechT5-VC processor from %s", self._model_name)
            self._processor = SpeechT5Processor.from_pretrained(self._model_name)

            logger.info("Loading SpeechT5-VC model from %s", self._model_name)
            self._model = SpeechT5ForSpeechToSpeech.from_pretrained(self._model_name).to(self._device)

            logger.info("Loading SpeechT5 HiFi-GAN vocoder from %s", self._vocoder_name)
            self._vocoder = SpeechT5HifiGan.from_pretrained(self._vocoder_name).to(self._device)

            self._initialized = True
            logger.info("SpeechT5-VC adapter initialized successfully on %s", self._device)
        except Exception as exc:
            logger.error("Failed to initialize SpeechT5-VC components: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Failed to load SpeechT5-VC models: {exc}",
                cause=exc,
            ) from exc

    def _apply_expression(
        self,
        samples: Any,
        sample_rate: int,
        context: Optional[Dict[str, Any]],
    ) -> Any:
        """Apply expression controls to synthesized float32 audio samples.

        Uses torchaudio for pitch-shift and scipy.signal for time-stretch resampling.
        """
        if not context or "expression" not in context:
            return samples

        expr = context["expression"]
        pitch_scale = expr.get("pitch_scale", 1.0)
        rate_scale = expr.get("rate_scale", 1.0)
        energy_scale = expr.get("energy_scale", 1.0)

        if pitch_scale == 1.0 and rate_scale == 1.0 and energy_scale == 1.0:
            return samples

        import torch
        import numpy as np

        # Convert to 1D torch float tensor
        y = torch.as_tensor(samples, dtype=torch.float32)

        # 1. Rate (time-stretch / speed modulation via scipy resample)
        if rate_scale != 1.0 and len(y) > 0:
            import scipy.signal
            target_length = int(round(len(y) / float(rate_scale)))
            if target_length > 0:
                y_np = scipy.signal.resample(y.numpy(), target_length)
                y = torch.from_numpy(y_np).to(torch.float32)

        # 2. Pitch shift (via torchaudio.functional.pitch_shift)
        if pitch_scale != 1.0 and len(y) > 0:
            try:
                import torchaudio.functional as F
                n_steps = 12.0 * math.log2(pitch_scale)
                # pitch_shift expects shape [..., time]
                y = F.pitch_shift(y.unsqueeze(0), sample_rate=sample_rate, n_steps=n_steps).squeeze(0)
            except Exception as e:
                logger.warning("Torchaudio pitch shift failed in SpeechT5-VC, fallback: %s", e)

        # 3. Energy (amplitude scale)
        if energy_scale != 1.0 and len(y) > 0:
            y = y * float(energy_scale)
            y = torch.clamp(y, -1.0, 1.0)

        return y.numpy()

    def convert(
        self,
        source_audio_bytes: bytes,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        if not self.is_available():
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message="PyTorch or Transformers is not installed in the current environment.",
            )

        # 1. Fast Validation: Resolve target speaker representation/embedding vector first
        rep_data = voice_config.get("representation_data")
        if not rep_data:
            rep_data = voice_config.get("speaker_embedding")

        if not rep_data:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="SpeechT5-VC requires target voice representation data for identity conditioning.",
                details={"voice_config_keys": list(voice_config.keys())},
            )

        # Deserialize embedding (512 float32 elements)
        if isinstance(rep_data, bytes):
            n_floats = len(rep_data) // 4
            embedding_vector = list(struct.unpack(f"<{n_floats}f", rep_data))
        elif isinstance(rep_data, list):
            embedding_vector = rep_data
        else:
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Target representation data is in an unsupported format",
            )

        if len(embedding_vector) != 512:
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"SpeechT5 requires 512-dimensional speaker embeddings, got {len(embedding_vector)}.",
            )

        # 2. Extract and decode source audio waveform
        try:
            import numpy as np
            with wave.open(io.BytesIO(source_audio_bytes), "rb") as wf:
                channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                raw_audio = wf.readframes(n_frames)

            waveform = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32767.0
            if channels > 1:
                waveform = waveform.reshape(-1, channels).mean(axis=1)

            # SpeechT5-VC expects 16kHz audio input
            if sample_rate != 16000:
                from scipy import signal
                num_samples = int(len(waveform) * 16000 / sample_rate)
                waveform = signal.resample(waveform, num_samples)
                sample_rate = 16000
        except Exception as exc:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message=f"Invalid source audio data: {exc}",
                cause=exc,
            ) from exc

        # 3. Lazy component loading (only after inputs and target representation are validated)
        self._load_components()

        import torch

        try:
            # Shape for SpeechT5 target identity: [1, 512]
            spk_emb = torch.tensor(embedding_vector, dtype=torch.float32).unsqueeze(0).to(self._device)

            # Process inputs and perform neural speech-to-speech voice conversion
            inputs = self._processor(audio=waveform, sampling_rate=16000, return_tensors="pt").to(self._device)

            with torch.no_grad():
                speech_tensor = self._model.generate_speech(
                    inputs["input_values"],
                    spk_emb,
                    vocoder=self._vocoder,
                )
                speech_samples = speech_tensor.cpu().numpy()

            # 4. Apply S2 request-time expression controls via context
            speech_samples = self._apply_expression(speech_samples, 16000, context)

            # 5. Re-serialize output waveform to 16-bit PCM WAV format
            wav_buf = io.BytesIO()
            n_out_frames = len(speech_samples)
            scaled_samples = []
            for sample in speech_samples:
                clamped = max(-1.0, min(1.0, float(sample)))
                scaled_samples.append(int(clamped * 32767))

            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(struct.pack(f"<{n_out_frames}h", *scaled_samples))

            wav_bytes = wav_buf.getvalue()
            duration_sec = float(n_out_frames / 16000)

            logger.debug("SpeechT5 voice conversion complete | bytes=%d duration=%.2fs", len(wav_bytes), duration_sec)

            return RenderResult(
                audio_bytes=wav_bytes,
                audio_format="wav",
                sample_rate=16000,
                duration_seconds=duration_sec,
                metadata={
                    "renderer": "speecht5_vc",
                    "device": self._device,
                    "target_embedding_dim": len(embedding_vector),
                    "sample_rate": 16000,
                },
            )
        except Exception as exc:
            logger.error("SpeechT5 neural voice conversion failed: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"SpeechT5 neural conversion failed: {exc}",
                cause=exc,
            ) from exc