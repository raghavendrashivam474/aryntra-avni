"""Voice Capability — main orchestration entry point for TTS and Voice Conversion.

Flow:
    validate request  →  resolve identity (Registry / ProfileStore)  →  resolve renderer/converter  →  invoke (with fallback)  →  respond
"""

import logging
import time
from typing import Optional

from src.contracts.voice import VoiceRequest, VoiceResponse, VoiceIdentity, VoiceConversionRequest
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.contracts.renderer import RenderResult, TTSRenderer, VoiceConverter
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry, ConverterRegistry
from src.capabilities.voice.identity_loader import IdentityLoader
from src.profiles.profile_store import ProfileStore

logger = logging.getLogger(__name__)


class VoiceCapability:
    """Public surface that NAV (or any consumer) calls to synthesize or convert speech."""

    def __init__(
        self,
        identity_registry: Optional[IdentityRegistry] = None,
        renderer_registry: Optional[RendererRegistry] = None,
        converter_registry: Optional[ConverterRegistry] = None,
        profile_store: Optional[ProfileStore] = None,
    ) -> None:
        self.identities = identity_registry or IdentityRegistry()
        self.renderers = renderer_registry or RendererRegistry()
        self.converters = converter_registry or ConverterRegistry()
        self.profile_store = profile_store

    def _resolve_identity(self, identity_id: str) -> VoiceIdentity:
        """Resolve identity from in-memory registry or on-demand from ProfileStore."""
        if self.identities.exists(identity_id):
            return self.identities.get(identity_id)

        if self.profile_store and self.profile_store.exists(identity_id):
            logger.info("Resolving identity '%s' from persistent ProfileStore", identity_id)
            profile = self.profile_store.load(identity_id)
            identity = IdentityLoader.load_from_profile(profile)
            # Register in-memory for subsequent fast-path hits
            self.identities.register(identity)
            return identity

        raise AvniVoiceError(
            code=VoiceErrorCode.UNKNOWN_IDENTITY,
            message=f"Voice identity '{identity_id}' is not registered or found in profile store.",
            details={"identity_id": identity_id},
        )

    def _render_with_renderer(
        self,
        renderer: TTSRenderer,
        text: str,
        voice_config: dict,
        context: Optional[dict],
        identity_id: str,
    ) -> RenderResult:
        try:
            return renderer.render(
                text=text,
                voice_config=voice_config,
                context=context,
            )
        except AvniVoiceError:
            raise
        except Exception as exc:
            logger.error("Renderer '%s' execution failed: %s", renderer.renderer_id, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"Renderer '{renderer.renderer_id}' failed: {exc}",
                details={
                    "identity_id": identity_id,
                    "renderer_id": renderer.renderer_id,
                },
                cause=exc,
            ) from exc

    def _convert_with_converter(
        self,
        converter: VoiceConverter,
        source_audio_bytes: bytes,
        voice_config: dict,
        context: Optional[dict],
        identity_id: str,
    ) -> RenderResult:
        try:
            return converter.convert(
                source_audio_bytes=source_audio_bytes,
                voice_config=voice_config,
                context=context,
            )
        except AvniVoiceError:
            raise
        except Exception as exc:
            logger.error("Voice converter '%s' execution failed: %s", converter.converter_id, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"Voice converter '{converter.converter_id}' failed: {exc}",
                details={
                    "identity_id": identity_id,
                    "converter_id": converter.converter_id,
                },
                cause=exc,
            ) from exc

    def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        """End-to-end speech synthesis with profile resolution and fallback resilience."""
        t0 = time.perf_counter()
        req_label = request.request_id or "anonymous"
        logger.info("Synthesis started | request=%s identity=%s", req_label, request.identity_id)

        # 1 — validate
        request.validate()

        # 2 — resolve identity
        identity = self._resolve_identity(request.identity_id)

        # 3 — attempt primary renderer
        primary_error: Optional[Exception] = None
        result: Optional[RenderResult] = None
        actual_renderer_id = identity.renderer_id
        fallback_used = False

        try:
            primary_renderer = self.renderers.get(identity.renderer_id)
            result = self._render_with_renderer(
                renderer=primary_renderer,
                text=request.text,
                voice_config=identity.voice_configuration,
                context=request.context,
                identity_id=identity.identity_id,
            )
        except Exception as exc:
            primary_error = exc
            logger.warning(
                "Primary renderer '%s' failed for identity '%s' | error=%s",
                identity.renderer_id, identity.identity_id, exc,
            )

        # 4 — fallback evaluation
        if result is None:
            if identity.fallback_renderer_id:
                logger.info(
                    "Attempting fallback to '%s' for identity '%s'",
                    identity.fallback_renderer_id, identity.identity_id,
                )
                try:
                    fallback_renderer = self.renderers.get(identity.fallback_renderer_id)
                    result = self._render_with_renderer(
                        renderer=fallback_renderer,
                        text=request.text,
                        voice_config=identity.fallback_voice_configuration,
                        context=request.context,
                        identity_id=identity.identity_id,
                    )
                    actual_renderer_id = identity.fallback_renderer_id
                    fallback_used = True
                    logger.info("Fallback synthesis succeeded with '%s'", actual_renderer_id)
                except Exception as fb_exc:
                    logger.error("Fallback renderer '%s' also failed: %s", identity.fallback_renderer_id, fb_exc)
                    raise AvniVoiceError(
                        code=VoiceErrorCode.GENERATION_FAILURE,
                        message=f"Primary renderer '{identity.renderer_id}' failed ({primary_error}) and fallback '{identity.fallback_renderer_id}' also failed: {fb_exc}",
                        details={
                            "identity_id": identity.identity_id,
                            "primary_renderer_id": identity.renderer_id,
                            "fallback_renderer_id": identity.fallback_renderer_id,
                            "primary_error": str(primary_error),
                            "fallback_error": str(fb_exc),
                        },
                        cause=fb_exc,
                    ) from fb_exc
            else:
                if isinstance(primary_error, AvniVoiceError):
                    raise primary_error
                raise AvniVoiceError(
                    code=VoiceErrorCode.GENERATION_FAILURE,
                    message=f"Renderer '{identity.renderer_id}' failed: {primary_error}",
                    details={
                        "identity_id": identity.identity_id,
                        "renderer_id": identity.renderer_id,
                    },
                    cause=primary_error,
                ) from primary_error

        elapsed = time.perf_counter() - t0

        # 5 — construct stable response
        metadata = dict(result.metadata)
        metadata.update(
            identity_id=identity.identity_id,
            renderer_id=actual_renderer_id,
            primary_renderer_id=identity.renderer_id,
            fallback_used=fallback_used,
            generation_latency_sec=round(elapsed, 4),
        )
        if identity.representation_id:
            metadata["representation_id"] = identity.representation_id
        if identity.profile_id:
            metadata["profile_id"] = identity.profile_id

        logger.info(
            "Synthesis complete | request=%s latency=%.3fs bytes=%d fallback=%s renderer=%s",
            req_label, elapsed, len(result.audio_bytes), fallback_used, actual_renderer_id,
        )

        return VoiceResponse(
            audio_bytes=result.audio_bytes,
            audio_format=result.audio_format,
            sample_rate=result.sample_rate,
            duration_seconds=result.duration_seconds,
            metadata=metadata,
            request_id=request.request_id,
        )

    def convert(self, request: VoiceConversionRequest) -> VoiceResponse:
        """End-to-end voice conversion with target profile resolution and fallback resilience."""
        t0 = time.perf_counter()
        req_label = request.request_id or "anonymous"
        logger.info("Voice conversion started | request=%s target_identity=%s", req_label, request.target_identity_id)

        # 1 — validate
        request.validate()

        # 2 — resolve target identity
        identity = self._resolve_identity(request.target_identity_id)

        # 3 — determine primary converter from configuration or identity context
        # If the target identity specifies a neural_xvector, we try to route to our neural converter (speecht5_vc)
        primary_converter_id = "speecht5_vc"
        fallback_converter_id = "acoustic_vc"

        if identity.renderer_id == "piper" or identity.renderer_id == "edge_tts":
            # For non-neural target voices, default directly to spectral/acoustic conversion adapter
            primary_converter_id = "acoustic_vc"
            fallback_converter_id = None

        primary_error: Optional[Exception] = None
        result: Optional[RenderResult] = None
        actual_converter_id = primary_converter_id
        fallback_used = False

        # 4 — attempt primary voice converter execution
        try:
            primary_converter = self.converters.get(primary_converter_id)
            result = self._convert_with_converter(
                converter=primary_converter,
                source_audio_bytes=request.source_audio_bytes,
                voice_config=identity.voice_configuration,
                context=request.context,
                identity_id=identity.identity_id,
            )
        except Exception as exc:
            primary_error = exc
            logger.warning(
                "Primary voice converter '%s' failed for target identity '%s' | error=%s",
                primary_converter_id, identity.identity_id, exc,
            )

        # 5 — fallback execution evaluation
        if result is None:
            if fallback_converter_id:
                logger.info(
                    "Attempting fallback voice conversion to '%s' for target identity '%s'",
                    fallback_converter_id, identity.identity_id,
                )
                try:
                    fallback_converter = self.converters.get(fallback_converter_id)
                    result = self._convert_with_converter(
                        converter=fallback_converter,
                        source_audio_bytes=request.source_audio_bytes,
                        voice_config=identity.voice_configuration,
                        context=request.context,
                        identity_id=identity.identity_id,
                    )
                    actual_converter_id = fallback_converter_id
                    fallback_used = True
                    logger.info("Fallback voice conversion succeeded with '%s'", actual_converter_id)
                except Exception as fb_exc:
                    logger.error("Fallback voice converter '%s' also failed: %s", fallback_converter_id, fb_exc)
                    raise AvniVoiceError(
                        code=VoiceErrorCode.GENERATION_FAILURE,
                        message=f"Primary converter '{primary_converter_id}' failed ({primary_error}) and fallback '{fallback_converter_id}' also failed: {fb_exc}",
                        details={
                            "identity_id": identity.identity_id,
                            "primary_converter_id": primary_converter_id,
                            "fallback_converter_id": fallback_converter_id,
                            "primary_error": str(primary_error),
                            "fallback_error": str(fb_exc),
                        },
                        cause=fb_exc,
                    ) from fb_exc
            else:
                if isinstance(primary_error, AvniVoiceError):
                    raise primary_error
                raise AvniVoiceError(
                    code=VoiceErrorCode.GENERATION_FAILURE,
                    message=f"Voice converter '{primary_converter_id}' failed: {primary_error}",
                    details={
                        "identity_id": identity.identity_id,
                        "converter_id": primary_converter_id,
                    },
                    cause=primary_error,
                ) from primary_error

        elapsed = time.perf_counter() - t0

        # 6 — construct stable VoiceResponse structure matching standard outputs
        metadata = dict(result.metadata)
        metadata.update(
            identity_id=identity.identity_id,
            converter_id=actual_converter_id,
            primary_converter_id=primary_converter_id,
            fallback_used=fallback_used,
            conversion_latency_sec=round(elapsed, 4),
        )
        if identity.representation_id:
            metadata["representation_id"] = identity.representation_id
        if identity.profile_id:
            metadata["profile_id"] = identity.profile_id

        logger.info(
            "Voice conversion complete | request=%s latency=%.3fs bytes=%d fallback=%s converter=%s",
            req_label, elapsed, len(result.audio_bytes), fallback_used, actual_converter_id,
        )

        return VoiceResponse(
            audio_bytes=result.audio_bytes,
            audio_format=result.audio_format,
            sample_rate=result.sample_rate,
            duration_seconds=result.duration_seconds,
            metadata=metadata,
            request_id=request.request_id,
        )
