# ADR-0012: Voice Conversion Abstraction for V2.5

**Status:** Accepted
**Date:** 2026-09-09
**Supersedes:** None
**Relates to:** ADR-0003 (Voice Capability Contract), ADR-0010 (Voice Identity Primitive)

## Context

V2.5 introduces speech-to-speech voice conversion as a second
manifestation pathway alongside the existing TTS pathway.

The existing `TTSRenderer` contract defines:
render(text: str, voice_config: dict, context: dict) -> RenderResult

text


Voice conversion requires:
convert(source_audio: bytes, target_voice_config: dict, context: dict) -> RenderResult

text


The input modality is fundamentally different (text vs audio).

## Decision

**Option B: Introduce a dedicated `VoiceConverter` abstraction**
as a sibling to `TTSRenderer`, sharing `RenderResult` as output.

### New Contracts

1. `VoiceConverter` (ABC in contracts/renderer.py)
   - `convert(source_audio_bytes, voice_config, context) -> RenderResult`
   - `converter_id: str`
   - `is_available() -> bool`

2. `VoiceConversionRequest` (dataclass in contracts/voice.py)
   - `target_identity_id: str`
   - `source_audio_bytes: bytes`
   - `source_audio_format: str`
   - `source_sample_rate: int`
   - `context: dict`

### Integration

- `VoiceCapability` gains a `convert()` method alongside `synthesize()`
- `ConverterRegistry` stores `VoiceConverter` instances
- Identity resolution reuses existing `_resolve_identity()` pipeline
- `RenderResult` is shared between TTS and VC outputs

## Consequences

### Positive
- Clean semantic separation between TTS and VC
- No modification to existing TTS contracts
- VC implementation remains replaceable
- Same identity resolution pipeline for both pathways
- `RenderResult` reuse avoids output duplication

### Negative
- Two parallel registries (renderers + converters)
- `VoiceCapability` grows slightly larger
- New abstraction to maintain

### Risks
- If TTS and VC later need unified handling, we may need
  a broader abstraction (Option C). But we do not preempt this.

## Alternatives Considered

### Option A: Extend TTSRenderer
Rejected. The `text` parameter is semantically incompatible
with source audio input. Would require union types or optional
parameters that obscure the contract.

### Option C: Unified ManifestationRenderer
Rejected. No evidence yet that TTS and VC share a stable
abstraction beyond output format. Architecture should be
earned by the problem, not anticipated.
