"""Edge-TTS concrete adapter for Avni.

Translates Avni TTSRenderer calls to Microsoft Edge TTS neural voices.
"""

import asyncio
from typing import Any, Dict, Optional

from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode


class EdgeTTSAdapter(TTSRenderer):
    """Adapter for edge-tts neural voice generation."""

    DEFAULT_VOICE = "en-US-AriaNeural"
    DEFAULT_RATE = "+0%"
    DEFAULT_PITCH = "+0Hz"

    def __init__(self, default_voice: Optional[str] = None):
        self._default_voice = default_voice or self.DEFAULT_VOICE

    @property
    def renderer_id(self) -> str:
        return "edge_tts"

    def is_available(self) -> bool:
        try:
            import edge_tts
            return True
        except ImportError:
            return False

    def render(
        self,
        text: str,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        try:
            import edge_tts
        except ImportError as e:
            raise AvniVoiceError(
                code=VoiceErrorCode.RENDERER_UNAVAILABLE,
                message="edge-tts package is not installed in the environment.",
                cause=e,
            )

        voice = voice_config.get("voice", self._default_voice)
        rate = voice_config.get("rate", self.DEFAULT_RATE)
        pitch = voice_config.get("pitch", self.DEFAULT_PITCH)

        async def _synthesize() -> bytes:
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            audio_stream = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_stream.extend(chunk["data"])
            return bytes(audio_stream)

        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    audio_data = pool.submit(asyncio.run, _synthesize()).result()
            else:
                audio_data = asyncio.run(_synthesize())

            if not audio_data:
                raise AvniVoiceError(
                    code=VoiceErrorCode.GENERATION_FAILURE,
                    message="edge-tts returned empty audio stream.",
                    details={"voice": voice, "text_len": len(text)},
                )

            return RenderResult(
                audio_bytes=audio_data,
                audio_format="mp3",
                sample_rate=24000,
                duration_seconds=None,
                metadata={
                    "engine": "edge_tts",
                    "voice": voice,
                    "rate": rate,
                    "pitch": pitch,
                    "bytes_count": len(audio_data),
                },
            )

        except AvniVoiceError:
            raise
        except Exception as exc:
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"edge-tts failed to synthesize: {str(exc)}",
                details={"voice": voice},
                cause=exc,
            ) from exc