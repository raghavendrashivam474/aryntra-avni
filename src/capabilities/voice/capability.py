"""Voice Capability — main orchestration entry point.

Flow:
    validate request  →  resolve identity  →  resolve renderer  →  invoke (with fallback)  →  respond
"""

import logging
import time
from typing import Optional

from src.contracts.voice import VoiceRequest, VoiceResponse, VoiceIdentity
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.contracts.renderer import RenderResult, TTSRenderer
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry

logger = logging.getLogger(__name__)


class VoiceCapability:
    """Public surface that NAV (or any consumer) calls to synthesize speech."""

    def __init__(
        self,
        identity_registry: Optional[IdentityRegistry] = None,
        renderer_registry: Optional[RendererRegistry] = None,
    ) -> None:
        self.identities = identity_registry or IdentityRegistry()
        self.renderers = renderer_registry or RendererRegistry()

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

    def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        """End-to-end speech synthesis with fallback resilience."""
        t0 = time.perf_counter()
        req_label = request.request_id or "anonymous"
        logger.info("Synthesis started | request=%s identity=%s", req_label, request.identity_id)

        # 1 — validate
        request.validate()

        # 2 — resolve identity
        identity = self.identities.get(request.identity_id)

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
                # No fallback configured — re-raise primary failure
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