"""Piper TTS concrete adapter for Avni.

Translates Avni TTSRenderer calls to local offline Piper ONNX neural voices.
Runs completely offline on CPU.
"""

import io
import logging
import wave
from pathlib import Path
from typing import Any, Dict, Optional

from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode

logger = logging.getLogger(__name__)

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "voices" / "en_US-lessac-medium.onnx"


class PiperTTSAdapter(TTSRenderer):
    """Adapter for local offline Piper TTS neural voice generation."""

    def __init__(self, default_model_path: Optional[Path] = None):
        self._default_model_path = Path(default_model_path) if default_model_path else DEFAULT_MODEL_PATH
        self._loaded_voices: Dict[str, Any] = {}

    @property
    def renderer_id(self) -> str:
        return "piper"

    def is_available(self) -> bool:
        try:
            import piper
            return True
        except ImportError:
            return False

    def _get_voice(self, model_path: Path):
        model_key = str(model_path.resolve())
        if model_key not in self._loaded_voices:
            if not model_path.is_file():
                raise AvniVoiceError(
                    code=VoiceErrorCode.CONFIGURATION_FAILURE,
                    message=f"Piper voice model file not found: {model_path}",
                    details={"model_path": str(model_path)},
                )
            try:
                import piper
                logger.debug("Loading Piper model from %s", model_path)
                self._loaded_voices[model_key] = piper.PiperVoice.load(str(model_path))
            except Exception as exc:
                raise AvniVoiceError(
                    code=VoiceErrorCode.CONFIGURATION_FAILURE,
                    message=f"Failed to load Piper model from '{model_path}': {exc}",
                    details={"model_path": str(model_path)},
                    cause=exc,
                ) from exc

        return self._loaded_voices[model_key]

    def render(
        self,
        text: str,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        if not self.is_available():
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message="piper-tts package is not installed in the environment.",
            )

        model_path_str = voice_config.get("model_path")
        model_path = Path(model_path_str) if model_path_str else self._default_model_path

        logger.debug("PiperTTS render | model=%s text_len=%d", model_path.name, len(text))

        try:
            voice = self._get_voice(model_path)
            buf = io.BytesIO()

            with wave.open(buf, "wb") as wav_file:
                voice.synthesize_wav(text, wav_file)

            audio_data = buf.getvalue()

            if not audio_data or len(audio_data) <= 44:  # 44 bytes is just a blank WAV header
                raise AvniVoiceError(
                    code=VoiceErrorCode.GENERATION_FAILURE,
                    message="Piper returned empty audio stream.",
                    details={"model": str(model_path), "text_len": len(text)},
                )

            sample_rate = voice.config.sample_rate

            logger.debug("PiperTTS render complete | bytes=%d sample_rate=%d", len(audio_data), sample_rate)

            return RenderResult(
                audio_bytes=audio_data,
                audio_format="wav",
                sample_rate=sample_rate,
                duration_seconds=None,
                metadata={
                    "engine": "piper",
                    "model": model_path.name,
                    "bytes_count": len(audio_data),
                },
            )

        except AvniVoiceError:
            raise
        except Exception as exc:
            logger.error("PiperTTS render failed | model=%s error=%s", model_path, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"piper-tts failed to synthesize: {str(exc)}",
                details={"model": str(model_path)},
                cause=exc,
            ) from exc
