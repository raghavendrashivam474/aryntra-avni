"""SpeechT5 Text-to-Speech Adapter (V1.5 & V3.0 S1).

Manifests persistent Voice Identity profiles into speech audio
conditioned on real 512-dimensional speaker embedding vectors.

In V3.0 S1, supports request-time ExpressionConfig via context
propagation, applying post-synthesis pitch, rate, and energy
modifications without altering the persistent identity embedding.
"""

import io
import logging
import math
import struct
import wave
from typing import Any, Dict, Optional

from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode

logger = logging.getLogger(__name__)


class SpeechT5TTSAdapter(TTSRenderer):
    """SpeechT5 neural TTS renderer with speaker embedding conditioning."""

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

    def _apply_expression(
        self,
        samples: Any,
        sample_rate: int,
        context: Optional[Dict[str, Any]],
    ) -> Any:
        """Apply expression controls to synthesized float32 audio samples.

        SpeechT5 vocoder output is post-processed via librosa for
        time-stretch (rate), pitch shift (pitch), and amplitude scaling (energy).
        """
        if not context or "expression" not in context:
            return samples

        expr = context["expression"]
        pitch_scale = expr.get("pitch_scale", 1.0)
        rate_scale = expr.get("rate_scale", 1.0)
        energy_scale = expr.get("energy_scale", 1.0)

        if pitch_scale == 1.0 and rate_scale == 1.0 and energy_scale == 1.0:
            return samples

        try:
            import numpy as np
            import librosa
        except ImportError:
            logger.warning("librosa/numpy not available; skipping expression post-processing")
            return samples

        y = np.array(samples, dtype=np.float32)

        # Rate (time stretch)
        if rate_scale != 1.0:
            y = librosa.effects.time_stretch(y=y, rate=rate_scale)

        # Pitch shift
        if pitch_scale != 1.0:
            n_steps = 12.0 * math.log2(pitch_scale)
            y = librosa.effects.pitch_shift(y=y, sr=sample_rate, n_steps=n_steps)

        # Energy (amplitude scaling)
        if energy_scale != 1.0:
            y = y * energy_scale
            y = np.clip(y, -1.0, 1.0)

        return y

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
        import numpy as np

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
                speech_samples = speech_tensor.cpu().numpy()

            # 3. Apply S1 expression control via context if requested
            sample_rate = 16000
            speech_samples = self._apply_expression(speech_samples, sample_rate, context)

            # 4. Serialize generated raw float32 samples to 16-bit PCM WAV bytes (16000Hz)
            wav_buf = io.BytesIO()
            n_frames = len(speech_samples)
            scaled_samples = []
            for sample in speech_samples:
                clamped = max(-1.0, min(1.0, float(sample)))
                scaled_samples.append(int(clamped * 32767))

            with wave.open(wav_buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(struct.pack(f"<{n_frames}h", *scaled_samples))

            wav_bytes = wav_buf.getvalue()

            logger.debug(
                "SpeechT5 synthesis complete | bytes=%d duration=%.2f sec",
                len(wav_bytes),
                n_frames / sample_rate,
            )

            return RenderResult(
                audio_bytes=wav_bytes,
                audio_format="wav",
                sample_rate=sample_rate,
                duration_seconds=float(n_frames / sample_rate),
                metadata={
                    "engine": "speecht5",
                    "embedding_dim": len(embedding_vector),
                    "sample_rate": sample_rate,
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
