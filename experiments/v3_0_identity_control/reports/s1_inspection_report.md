# S1 Pre-Implementation Inspection Report

Generated: 2026-09-14 09:09:25

## Group A — Public Contracts

### src/contracts/voice.py

```python
﻿"""Voice Request, Response, and Identity contracts.

These are the public data structures that NAV and any other consumer
interacts with. They must remain stable across renderer changes.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class VoiceRequest:
    """Inbound request for speech synthesis."""

    text: str
    identity_id: str
    request_id: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    streaming: bool = False

    def validate(self) -> None:
        """Raises AvniVoiceError(INVALID_REQUEST) if invariants are violated."""
        from src.contracts.errors import AvniVoiceError, VoiceErrorCode

        if not isinstance(self.text, str) or not self.text.strip():
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="text must be a non-empty string.",
                details={"field": "text", "value": repr(self.text)},
            )
        if not isinstance(self.identity_id, str) or not self.identity_id.strip():
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="identity_id must be a non-empty string.",
                details={"field": "identity_id", "value": repr(self.identity_id)},
            )


@dataclass(frozen=True)
class VoiceResponse:
    """Outbound response containing generated audio."""

    audio_bytes: bytes
    audio_format: str          # e.g. "wav", "pcm", "mp3"
    sample_rate: int
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    request_id: Optional[str] = None


@dataclass(frozen=True)
class VoiceIdentity:
    """Stable representation of a voice identity.

    Independent of any specific TTS engine. The renderer_id links
    this identity to a registered TTSRenderer adapter.
    """

    identity_id: str
    renderer_id: str
    voice_configuration: Dict[str, Any] = field(default_factory=dict)
    provenance: Optional[Dict[str, Any]] = None
    fallback_renderer_id: Optional[str] = None
    fallback_voice_configuration: Dict[str, Any] = field(default_factory=dict)
    representation_id: Optional[str] = None
    profile_id: Optional[str] = None


# ============================================================
# V2.5: Voice Conversion Request
# ============================================================
# Sibling to VoiceRequest. Used for speech-to-speech conversion.
# See ADR-0012 for rationale.

@dataclass
class VoiceConversionRequest:
    """Request to convert source speech into a target voice identity."""
    target_identity_id: str
    source_audio_bytes: bytes
    source_audio_format: str = "wav"
    source_sample_rate: int = 16000
    context: Optional[Dict[str, Any]] = None
    request_id: Optional[str] = None

    def validate(self) -> None:
        """Validate the conversion request."""
        if not self.target_identity_id or not self.target_identity_id.strip():
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="target_identity_id must be a non-empty string.",
            )
        if not self.source_audio_bytes or len(self.source_audio_bytes) < 100:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message="source_audio_bytes must contain valid audio data (minimum 100 bytes).",
            )
        if self.source_sample_rate < 8000 or self.source_sample_rate > 48000:
            raise AvniVoiceError(
                code=VoiceErrorCode.INVALID_REQUEST,
                message=f"source_sample_rate must be between 8000 and 48000, got {self.source_sample_rate}.",
            )

```



### src/contracts/renderer.py

```python
﻿"""Renderer interface contract.

Every TTS engine adapter must implement TTSRenderer.
The rest of Avni never imports a concrete adapter directly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RenderResult:
    """Raw output from a concrete TTS adapter."""

    audio_bytes: bytes
    audio_format: str
    sample_rate: int
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TTSRenderer(ABC):
    """Abstract contract for all speech-synthesis backends."""

    @property
    @abstractmethod
    def renderer_id(self) -> str:
        """Unique identifier for this renderer (e.g. 'piper', 'elevenlabs')."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the underlying engine is ready to synthesize."""
        ...

    @abstractmethod
    def render(
        self,
        text: str,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        """Synthesize *text* into audio.

        Args:
            text: The text to speak.
            voice_config: Identity-specific parameters forwarded from VoiceIdentity.
            context: Optional request-level context hints.

        Returns:
            A RenderResult containing raw audio bytes and metadata.

        Raises:
            AvniVoiceError: On any generation or configuration failure.
        """
        ...

# ============================================================
# V2.5: Voice Conversion Abstraction
# ============================================================
# Sibling to TTSRenderer. Shares RenderResult as output type.
# See ADR-0012 for rationale.

class VoiceConverter(ABC):
    """Abstract base for voice conversion adapters.

    Voice conversion transforms source speech to match a target
    voice identity while preserving linguistic content, timing,
    and prosodic structure.

    Unlike TTSRenderer (which takes text), VoiceConverter takes
    source audio as input.
    """

    @property
    @abstractmethod
    def converter_id(self) -> str:
        """Unique identifier for this voice converter implementation."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the converter's dependencies are satisfied."""
        ...

    @abstractmethod
    def convert(
        self,
        source_audio_bytes: bytes,
        voice_config: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> RenderResult:
        """Convert source speech to match the target voice identity.

        Args:
            source_audio_bytes: Raw audio bytes of the source speech.
            voice_config: Target identity configuration including
                'representation_data' (target speaker embedding)
                and optionally 'reference_audio_bytes' (target
                reference clip for model conditioning).
            context: Optional runtime context.

        Returns:
            RenderResult with converted audio.
        """
        ...

```



## Group B — Capability Orchestration

### src/capabilities/voice/capability.py

```python
﻿"""Voice Capability — main orchestration entry point for TTS and Voice Conversion.

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

```



### src/capabilities/voice/identity_loader.py

```python
﻿"""Identity Loader for Avni Voice configurations and profiles."""

import json
from pathlib import Path
from typing import Dict, List, Union, Optional

from src.contracts.voice import VoiceIdentity
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.profiles.voice_profile import VoiceIdentityProfile


class IdentityLoader:
    """Loads VoiceIdentity definitions from declarative files, directories, and profiles."""

    @staticmethod
    def load_from_dict(data: Dict) -> VoiceIdentity:
        """Parses a dictionary into a validated VoiceIdentity object."""
        if not isinstance(data, dict):
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Identity configuration data must be a dictionary.",
            )

        identity_id = data.get("identity_id")
        renderer_id = data.get("renderer_id")

        if not identity_id or not isinstance(identity_id, str):
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Identity configuration missing or invalid 'identity_id'.",
                details={"data": data},
            )

        if not renderer_id or not isinstance(renderer_id, str):
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message="Identity configuration missing or invalid 'renderer_id'.",
                details={"data": data},
            )

        return VoiceIdentity(
            identity_id=identity_id.strip(),
            renderer_id=renderer_id.strip(),
            voice_configuration=data.get("voice_configuration", {}),
            provenance=data.get("provenance", {}),
            fallback_renderer_id=data.get("fallback_renderer_id"),
            fallback_voice_configuration=data.get("fallback_voice_configuration", {}),
            representation_id=data.get("representation_id"),
            profile_id=data.get("profile_id"),
        )

    @staticmethod
    def load_from_profile(
        profile: VoiceIdentityProfile,
        default_renderer_id: str = "edge_tts",
        default_voice_config: Optional[Dict] = None,
        fallback_renderer_id: Optional[str] = "piper",
        fallback_voice_config: Optional[Dict] = None,
    ) -> VoiceIdentity:
        """Binds a persistent VoiceIdentityProfile to a synthesizable VoiceIdentity."""
        profile.validate()
        voice_cfg = default_voice_config or {}
        # Embed representation metadata into configuration for renderer context
        voice_cfg = dict(voice_cfg)
        voice_cfg["representation_id"] = profile.representation.representation_id
        voice_cfg["representation_version"] = profile.representation.version
        # Inject raw representation data bytes for downstream speaker-conditioned neural adapters
        voice_cfg["representation_data"] = profile.representation.data

        # Explicit routing: If neural representation, route default to SpeechT5
        resolved_renderer = default_renderer_id
        if profile.representation.representation_id and "neural_xvector" in profile.representation.representation_id:
            resolved_renderer = "speecht5"

        return VoiceIdentity(
            identity_id=profile.identity_id,
            renderer_id=resolved_renderer,
            voice_configuration=voice_cfg,
            provenance={
                "profile_schema_version": profile.schema_version,
                "consent_source_id": profile.consent.source_id,
                "provenance": profile.provenance.to_dict(),
            },
            fallback_renderer_id=fallback_renderer_id,
            fallback_voice_configuration=fallback_voice_config or {},
            representation_id=profile.representation.representation_id,
            profile_id=profile.identity_id,
        )

    @staticmethod
    def load_from_json_file(file_path: Union[str, Path]) -> VoiceIdentity:
        """Reads a JSON identity configuration file."""
        path = Path(file_path)
        if not path.is_file():
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Identity config file not found: {path}",
                details={"path": str(path)},
            )

        try:
            with open(path, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
            return IdentityLoader.load_from_dict(data)
        except json.JSONDecodeError as exc:
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Failed to parse identity JSON at '{path}': {str(exc)}",
                details={"path": str(path)},
                cause=exc,
            ) from exc

    @staticmethod
    def load_directory(dir_path: Union[str, Path]) -> List[VoiceIdentity]:
        """Loads all JSON identity profiles from a directory."""
        directory = Path(dir_path)
        if not directory.is_dir():
            raise AvniVoiceError(
                code=VoiceErrorCode.CONFIGURATION_FAILURE,
                message=f"Identities directory not found: {directory}",
                details={"directory": str(directory)},
            )

        identities = []
        for file in sorted(directory.glob("*.json")):
            identities.append(IdentityLoader.load_from_json_file(file))
        return identities

```



## Group C — TTS Adapters

### src/adapters/tts/speecht5_adapter.py

```python
﻿"""SpeechT5 concrete adapter for Avni.

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

```



### src/adapters/tts/edge_tts_adapter.py

```python
"""Edge-TTS concrete adapter for Avni.

Translates Avni TTSRenderer calls to Microsoft Edge TTS neural voices.
Designed for synchronous callers. Uses asyncio.run() internally.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode

logger = logging.getLogger(__name__)


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

        logger.debug("EdgeTTS render | voice=%s rate=%s pitch=%s text_len=%d",
                      voice, rate, pitch, len(text))

        async def _synthesize() -> bytes:
            communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)
            audio_stream = bytearray()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_stream.extend(chunk["data"])
            return bytes(audio_stream)

        try:
            audio_data = asyncio.run(_synthesize())

            if not audio_data:
                raise AvniVoiceError(
                    code=VoiceErrorCode.GENERATION_FAILURE,
                    message="edge-tts returned empty audio stream.",
                    details={"voice": voice, "text_len": len(text)},
                )

            logger.debug("EdgeTTS render complete | bytes=%d", len(audio_data))

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
            logger.error("EdgeTTS render failed | voice=%s error=%s", voice, exc)
            raise AvniVoiceError(
                code=VoiceErrorCode.GENERATION_FAILURE,
                message=f"edge-tts failed to synthesize: {str(exc)}",
                details={"voice": voice},
                cause=exc,
            ) from exc
```



## Group D — S0 Experiment Info

### experiments/v3_0_identity_control/README.md

```text
﻿# Aryntra Avni — V3.0 Identity Control Research Experiment

This directory contains the experimental harnesses, configurations, artifacts, and reports for the V3.0 Identity Control and Disentanglement Research Spike (S0).

## Directory Structure

```text
experiments/v3_0_identity_control/
├── config/       # Experiment configuration files
├── scripts/      # Standalone experiment execution scripts
│   └── run_disentanglement_experiment.py
├── results/      # Generated audio WAVs and raw metric JSONs
│   ├── output_converted_condition_1_source_b_eval_1.wav
│   ├── output_converted_condition_2_source_b_eval_2.wav
│   ├── output_converted_condition_3_source_b_eval_3.wav
│   └── s0_results.json
└── reports/      # Markdown synthesis and analysis
    └── v3_0_s0_research_report.md
How to Reproduce
PowerShell

python experiments/v3_0_identity_control/scripts/run_disentanglement_experiment.py

```



### experiments/v3_0_identity_control/scripts/run_disentanglement_experiment.py

```python
﻿"""
Aryntra Avni V3.0 S0 — Identity Control & Disentanglement Experiment.
Investigates whether Avni can vary voice expression while preserving persistent identity.
"""

import sys
import os
import json
import base64
import struct
import numpy as np
import wave
import io
import logging

# Set up logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v3_s0_experiment")

# Ensure repository root is in sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, repo_root)

try:
    from src.adapters.voice_conversion.speecht5_vc_adapter import SpeechT5VCAdapter
    from src.representation.neural_extractor import NeuralSpeakerExtractor
    from src.representation.base import VoiceRepresentation
    logger.info("Successfully imported Avni core modules.")
except ImportError as e:
    logger.error("Could not import Avni core modules: %s", e)
    sys.exit(1)


def load_profile_embedding(profile_path: str) -> VoiceRepresentation:
    """Load representation data directly from a persisted voice profile JSON."""
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    
    rep_dict = profile_data["representation"]
    data_bytes = base64.b64decode(rep_dict["data_b64"])
    
    return VoiceRepresentation(
        representation_id=rep_dict["representation_id"],
        version=rep_dict["version"],
        data=data_bytes,
        metadata=rep_dict.get("metadata", {})
    )


def extract_f0_features(audio_bytes: bytes) -> dict:
    """
    Compute basic pitch and temporal characteristics from raw WAV audio bytes
    to demonstrate acoustic changes across expression conditions.
    """
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_audio = wf.readframes(n_frames)
        
        waveform = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32767.0
        if channels > 1:
            waveform = waveform.reshape(-1, channels).mean(axis=1)
        
        duration = len(waveform) / sample_rate
        
        # Simple Autocorrelation-based pitch detector for rough F0 estimation
        frame_size = int(0.030 * sample_rate)  # 30ms frames
        hop_size = int(0.015 * sample_rate)   # 15ms hop
        f0s = []
        
        for i in range(0, len(waveform) - frame_size, hop_size):
            frame = waveform[i:i + frame_size]
            # Standard autocorrelation
            corr = np.correlate(frame, frame, mode="full")
            corr = corr[len(corr)//2:]
            
            # Find peaks corresponding to typical voice pitch (50Hz - 400Hz)
            min_lag = int(sample_rate / 400)
            max_lag = int(sample_rate / 50)
            
            if min_lag < len(corr):
                peak = np.argmax(corr[min_lag:min_lag + (max_lag - min_lag)]) + min_lag
                if corr[peak] > 0.15 * corr[0]:  # Voicing threshold
                    f0s.append(sample_rate / peak)
        
        if f0s:
            pitch_mean = float(np.mean(f0s))
            pitch_std = float(np.std(f0s))
            pitch_max = float(np.max(f0s))
        else:
            pitch_mean, pitch_std, pitch_max = 0.0, 0.0, 0.0
            
        # Energy metrics
        rms_energy = float(np.sqrt(np.mean(waveform ** 2)))
        
        return {
            "duration_sec": round(duration, 3),
            "pitch_mean_hz": round(pitch_mean, 2),
            "pitch_std_hz": round(pitch_std, 2),
            "pitch_max_hz": round(pitch_max, 2),
            "rms_energy": round(rms_energy, 4)
        }
    except Exception as e:
        logger.warning("Failed to extract acoustic metrics: %s", e)
        return {"error": str(e)}


def run_experiment():
    profile_path = os.path.join(repo_root, "data", "evaluation", "output", "profiles", "speaker_a.json")
    if not os.path.exists(profile_path):
        logger.error("Target speaker profile path does not exist: %s", profile_path)
        sys.exit(1)
        
    logger.info("Loading Target Speaker A Profile...")
    target_rep = load_profile_embedding(profile_path)
    
    # We will run 3 source audio files representing diverse speaking tempos/styles
    source_wav_paths = [
        os.path.join(repo_root, "data", "evaluation", "speaker_b", "evaluation", "eval_1.wav"),
        os.path.join(repo_root, "data", "evaluation", "speaker_b", "evaluation", "eval_2.wav"),
        os.path.join(repo_root, "data", "evaluation", "speaker_b", "evaluation", "eval_3.wav"),
    ]
    
    for path in source_wav_paths:
        if not os.path.exists(path):
            logger.error("Required source audio not found: %s", path)
            sys.exit(1)

    # Initialize neural modules
    logger.info("Initializing neural components (SpeechT5, SpeechBrain)...")
    converter = SpeechT5VCAdapter(device="cpu")
    extractor = NeuralSpeakerExtractor(device="cpu")
    
    # Run lazy-loading now to log setup progress
    converter._load_components()
    
    results = []
    
    for idx, src_path in enumerate(source_wav_paths):
        condition_name = f"condition_{idx + 1}_source_b_eval_{idx + 1}"
        logger.info("--- Processing Condition: %s ---", condition_name)
        
        with open(src_path, "rb") as f:
            source_bytes = f.read()
            
        source_metrics = extract_f0_features(source_bytes)
        logger.info("Source Audio Metrics: %s", source_metrics)
        
        # Perform Voice Conversion using the target representation
        voice_config = {
            "representation_data": target_rep.data
        }
        
        logger.info("Performing voice conversion to Target Identity...")
        render_result = converter.convert(source_bytes, voice_config)
        output_bytes = render_result.audio_bytes
        
        # Save output wav to the results folder
        out_wav_name = f"output_converted_{condition_name}.wav"
        out_wav_path = os.path.join(repo_root, "experiments", "v3_0_identity_control", "results", out_wav_name)
        with open(out_wav_path, "wb") as f_out:
            f_out.write(output_bytes)
            
        logger.info("Output saved to %s", out_wav_path)
        
        # Extract representation from the converted output to verify identity retention
        logger.info("Extracting identity representation from converted output...")
        output_rep = extractor.extract([output_bytes])
        
        # Calculate Cosine Similarity to Target Identity
        similarity_score = extractor.similarity(target_rep, output_rep)
        logger.info("Target Identity Retention Score: %.4f", similarity_score)
        
        # Extract output acoustic metrics
        output_metrics = extract_f0_features(output_bytes)
        logger.info("Converted Audio Metrics: %s", output_metrics)
        
        results.append({
            "condition": condition_name,
            "source_file": os.path.basename(src_path),
            "output_file": out_wav_name,
            "target_identity_similarity": round(similarity_score, 4),
            "source_metrics": source_metrics,
            "converted_metrics": output_metrics
        })
        
    # Write full analysis report
    report = {
        "experiment": "v3_0_s0_disentanglement_spike",
        "target_profile": "speaker_a",
        "status": "success",
        "results": results
    }
    
    report_json_path = os.path.join(repo_root, "experiments", "v3_0_identity_control", "results", "s0_results.json")
    with open(report_json_path, "w", encoding="utf-8") as f_rep:
        json.dump(report, f_rep, indent=2)
        
    logger.info("==========================================")
    logger.info("EXPERIMENT COMPLETE. Summary of results:")
    for res in results:
        logger.info(
            "Condition: %s | Similarity: %.2f%% | Source Pitch: %.1fHz -> Converted: %.1fHz",
            res["condition"],
            res["target_identity_similarity"] * 100,
            res["source_metrics"].get("pitch_mean_hz", 0),
            res["converted_metrics"].get("pitch_mean_hz", 0)
        )
    logger.info("Full experiment report saved to %s", report_json_path)


if __name__ == "__main__":
    run_experiment()

```



### experiments/v3_0_identity_control/results/s0_results.json

```text
{
  "experiment": "v3_0_s0_disentanglement_spike",
  "target_profile": "speaker_a",
  "status": "success",
  "results": [
    {
      "condition": "condition_1_source_b_eval_1",
      "source_file": "eval_1.wav",
      "output_file": "output_converted_condition_1_source_b_eval_1.wav",
      "target_identity_similarity": 0.9517,
      "source_metrics": {
        "duration_sec": 6.264,
        "pitch_mean_hz": 226.11,
        "pitch_std_hz": 87.87,
        "pitch_max_hz": 400.0,
        "rms_energy": 0.0755
      },
      "converted_metrics": {
        "duration_sec": 5.856,
        "pitch_mean_hz": 155.57,
        "pitch_std_hz": 86.07,
        "pitch_max_hz": 400.0,
        "rms_energy": 0.0908
      }
    },
    {
      "condition": "condition_2_source_b_eval_2",
      "source_file": "eval_2.wav",
      "output_file": "output_converted_condition_2_source_b_eval_2.wav",
      "target_identity_similarity": 0.9552,
      "source_metrics": {
        "duration_sec": 6.024,
        "pitch_mean_hz": 216.84,
        "pitch_std_hz": 90.08,
        "pitch_max_hz": 400.0,
        "rms_energy": 0.0804
      },
      "converted_metrics": {
        "duration_sec": 5.696,
        "pitch_mean_hz": 143.03,
        "pitch_std_hz": 73.31,
        "pitch_max_hz": 400.0,
        "rms_energy": 0.0812
      }
    },
    {
      "condition": "condition_3_source_b_eval_3",
      "source_file": "eval_3.wav",
      "output_file": "output_converted_condition_3_source_b_eval_3.wav",
      "target_identity_similarity": 0.9554,
      "source_metrics": {
        "duration_sec": 6.84,
        "pitch_mean_hz": 229.4,
        "pitch_std_hz": 89.31,
        "pitch_max_hz": 400.0,
        "rms_energy": 0.0849
      },
      "converted_metrics": {
        "duration_sec": 6.848,
        "pitch_mean_hz": 141.64,
        "pitch_std_hz": 64.17,
        "pitch_max_hz": 400.0,
        "rms_energy": 0.0656
      }
    }
  ]
}
```



## Inspection Summary

| File | Status |
|------|--------|
| `src/contracts/voice.py` | ✅ Found |
| `src/contracts/renderer.py` | ✅ Found |
| `src/capabilities/voice/capability.py` | ✅ Found |
| `src/capabilities/voice/identity_loader.py` | ✅ Found |
| `src/adapters/tts/speecht5_adapter.py` | ✅ Found |
| `src/adapters/tts/edge_tts_adapter.py` | ✅ Found |
| `experiments/v3_0_identity_control/README.md` | ✅ Found |
| `experiments/v3_0_identity_control/scripts/run_disentanglement_experiment.py` | ✅ Found |
| `experiments/v3_0_identity_control/results/s0_results.json` | ✅ Found |