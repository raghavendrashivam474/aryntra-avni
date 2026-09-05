"""SpeechT5 concrete adapter for Avni.

Translates Avni TTSRenderer calls to Microsoft SpeechT5 conditioned neural voices.
Runs offline or locally on CPU/GPU using transformers.
"""

import io
import logging
import struct
import wave
from typing import Any, Dict, Optional

from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode

logger = logging.getLogger(__name__)


class SpeechT5TTSAdapter(TTSRenderer):
    """Adapter for runtime speaker-conditioned SpeechT5 text-to-speech."""

    def __init__(
        self,
        default_processor_path: str = "microsoft/speecht5_tts",
        default_model_path: str = "microsoft/speecht5_tts",
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
    def renderer_id(self) -> str:
        return "speecht5"

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
            from transformers import SpeechT5Processor, SpeechT5ForTextToSpeech, SpeechT5HifiGan

            logger.info("Initializing SpeechT5 model elements on %s...", self._device)
            self._processor = SpeechT5Processor.from_pretrained(self._default_processor_path)
            self._model = SpeechT5ForTextToSpeech.from_pretrained(self._default_model_path).to(self._device)
            self._vocoder = SpeechT5HifiGan.from_pretrained(self._default_vocoder_path).to(self._device)
        except Exception as exc:
            logger.error("Failed to initialize SpeechT5 models: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message=f"SpeechT5 renderer components could not be loaded: {exc}",
                cause=exc,
            ) from exc

    def render(
        self,
        text: str,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        if not self.is_available():
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message="PyTorch or Transformers is not installed in the current environment.",
            )

        self._load_components()

        import torch

        # 1. Resolve speaker embedding/representation vector
        rep_data = voice_config.get("representation_data")
        if not rep_data:
            rep_data = voice_config.get("speaker_embedding")

        if not rep_data:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="SpeechT5 requires raw voice representation data for speaker conditioning.",
                details={"voice_config_keys": list(voice_config.keys())},
            )

        try:
            # De-serialize embedding (512 float32 elements = 2048 bytes)
            if isinstance(rep_data, bytes):
                n_floats = len(rep_data) // 4
                embedding_vector = list(struct.unpack(f"<{n_floats}f", rep_data))
            elif isinstance(rep_data, list):
                embedding_vector = rep_data
            else:
                raise ValueError("Representation data is in an unsupported format")

            if len(embedding_vector) != 512:
                raise AvniVoiceError(
                    code=VoiceErrorCode.CONFIGURATION_FAILURE,
                    message=f"SpeechT5 requires 512-dimensional speaker embeddings, got {len(embedding_vector)} dimensions.",
                )

            # Shape for SpeechT5: [1, 512]
            spk_emb = torch.tensor(embedding_vector, dtype=torch.float32).unsqueeze(0).to(self._device)

            # 2. Tokenize and synthesize
            inputs = self._processor(text=text, return_tensors="pt").to(self._device)

            with torch.no_grad():
                speech_tensor = self._model.generate_speech(
                    inputs["input_ids"],
                    spk_emb,
                    vocoder=self._vocoder,
                )
                speech_tensor = speech_tensor.cpu().numpy()

            # 3. Serialize generated raw float32 samples to 16-bit PCM WAV bytes (16000Hz)
            wav_buf = io.BytesIO()
            n_frames = len(speech_tensor)
            scaled_samples = []
            for sample in speech_tensor:
                clamped = max(-1.0, min(1.0, float(sample)))
                scaled_samples.append(int(clamped * 32767))

            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(struct.pack(f"<{n_frames}h", *scaled_samples))

            wav_bytes = wav_buf.getvalue()

            logger.debug("SpeechT5 synthesis complete | bytes=%d duration=%.2f sec",
                         len(wav_bytes), n_frames / 16000)

            return RenderResult(
                audio_bytes=wav_bytes,
                audio_format="wav",
                sample_rate=16000,
                duration_seconds=float(n_frames / 16000),
                metadata={
                    "engine": "speecht5",
                    "embedding_dim": len(embedding_vector),
                    "sample_rate": 16000,
                    "bytes_count": len(wav_bytes),
                },
            )

        except AvniVoiceError:
            raise
        except Exception as exc:
            logger.error("SpeechT5 rendering failed: %s", exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"SpeechT5 failed to synthesize voice: {exc}",
                cause=exc,
            ) from exc
