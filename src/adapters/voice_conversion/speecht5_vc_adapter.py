"""SpeechT5 concrete Voice Converter adapter for Avni.

Translates Avni VoiceConverter calls to Microsoft SpeechT5 conditioned neural voice conversion.
Runs fully locally on CPU/GPU.
"""

import io
import logging
import struct
import wave
from typing import Any, Dict, Optional

from src.contracts.renderer import VoiceConverter, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode

logger = logging.getLogger(__name__)


class SpeechT5VCAdapter(VoiceConverter):
    """Adapter for runtime speaker-conditioned SpeechT5 voice-to-voice conversion."""

    def __init__(
        self,
        default_processor_path: str = "microsoft/speecht5_vc",
        default_model_path: str = "microsoft/speecht5_vc",
        default_vocoder_path: str = "microsoft/speecht5_hifigan",
        device: Optional[str] = None,
    ) -> None:
        self._default_processor_path = default_processor_path
        self._default_model_path = default_model_path
        self._default_vocoder_path = default_vocoder_path
        self._device = device or "cpu"
        self._processor = None
        self._model = None
        self._vocoder = None

    @property
    def converter_id(self) -> str:
        return "speecht5_vc"

    def is_available(self) -> bool:
        try:
            import torch
            import transformers
            return True
        except ImportError:
            return False

    def _load_components(self) -> None:
        """Load and cache SpeechT5 models & components."""
        if self._model is not None:
            return

        try:
            import torch
            from transformers import SpeechT5Processor, SpeechT5ForSpeechToSpeech, SpeechT5HifiGan

            logger.info("Initializing SpeechT5 voice conversion models on %s...", self._device)
            self._processor = SpeechT5Processor.from_pretrained(self._default_processor_path)
            self._model = SpeechT5ForSpeechToSpeech.from_pretrained(self._default_model_path).to(self._device)
            self._vocoder = SpeechT5HifiGan.from_pretrained(self._default_vocoder_path).to(self._device)
        except Exception as exc:
            logger.error("Failed to initialize SpeechT5-VC models: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message=f"SpeechT5 voice conversion components could not be loaded: {exc}",
                cause=exc,
            ) from exc

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
                speech_tensor = speech_tensor.cpu().numpy()

            # 4. Re-serialize output waveform to 16-bit PCM WAV format
            wav_buf = io.BytesIO()
            n_out_frames = len(speech_tensor)
            scaled_samples = []
            for sample in speech_tensor:
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
                    "engine": "speecht5_vc",
                    "target_embedding_dim": len(embedding_vector),
                    "sample_rate": 16000,
                    "bytes_count": len(wav_bytes),
                    "duration_seconds": round(duration_sec, 3),
                },
            )

        except Exception as exc:
            logger.error("SpeechT5 voice conversion failed: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"SpeechT5 neural voice converter failed: {exc}",
                cause=exc,
            ) from exc
