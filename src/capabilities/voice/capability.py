"""Voice Capability — main orchestration entry point.

Flow:
    validate request  →  resolve identity  →  resolve renderer  →  invoke  →  respond
"""

import logging
import time
from typing import Optional

from src.contracts.voice import VoiceRequest, VoiceResponse
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
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

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def synthesize(self, request: VoiceRequest) -> VoiceResponse:
        """End-to-end speech synthesis.

        1. Validate the incoming request.
        2. Resolve the VoiceIdentity.
        3. Resolve the TTSRenderer linked to that identity.
        4. Invoke the renderer.
        5. Wrap the result in a stable VoiceResponse.
        """
        t0 = time.perf_counter()
        req_label = request.request_id or "anonymous"
        logger.info("Synthesis started | request=%s identity=%s", req_label, request.identity_id)

        # 1 — validate
        request.validate()

        # 2 — identity
        identity = self.identities.get(request.identity_id)

        # 3 — renderer
        renderer = self.renderers.get(identity.renderer_id)

        # 4 — invoke
        try:
            result = renderer.render(
                text=request.text,
                voice_config=identity.voice_configuration,
                context=request.context,
            )
        except AvniVoiceError:
            logger.error("Synthesis failed (domain error) | request=%s", req_label)
            raise
        except Exception as exc:
            logger.error("Synthesis failed (engine error) | request=%s renderer=%s error=%s",
                         req_label, identity.renderer_id, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"Renderer '{identity.renderer_id}' failed: {exc}",
                details={
                    "identity_id": identity.identity_id,
                    "renderer_id": identity.renderer_id,
                },
                cause=exc,
            ) from exc

        elapsed = time.perf_counter() - t0

        # 5 — response
        metadata = dict(result.metadata)
        metadata.update(
            identity_id=identity.identity_id,
            renderer_id=identity.renderer_id,
            generation_latency_sec=round(elapsed, 4),
        )

        logger.info("Synthesis complete | request=%s latency=%.3fs bytes=%d",
                     req_label, elapsed, len(result.audio_bytes))

        return VoiceResponse(
            audio_bytes=result.audio_bytes,
            audio_format=result.audio_format,
            sample_rate=result.sample_rate,
            duration_seconds=result.duration_seconds,
            metadata=metadata,
            request_id=request.request_id,
        )