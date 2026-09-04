"""Voice Capability — main orchestration entry point.

Flow:
    validate request  →  resolve identity  →  resolve renderer  →  invoke  →  respond
"""

import time
from typing import Optional

from src.contracts.voice import VoiceRequest, VoiceResponse
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry


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
            raise  # already a domain error — pass through
        except Exception as exc:
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

        return VoiceResponse(
            audio_bytes=result.audio_bytes,
            audio_format=result.audio_format,
            sample_rate=result.sample_rate,
            duration_seconds=result.duration_seconds,
            metadata=metadata,
            request_id=request.request_id,
        )