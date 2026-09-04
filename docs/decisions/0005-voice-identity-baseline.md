# ADR 0005: Voice Identity Baseline Configuration

## Context
Avni requires representing voice identities distinct from TTS renderers (Section 7, 8 of the brief).
In V0, we need a standard way to configure, persist, and load identities without hardcoding them into source code.

## Decision
1. Static voice identities are defined as declarative JSON configurations under `configs/identities/`.
2. `IdentityLoader` parses and validates configurations into immutable `VoiceIdentity` dataclasses.
3. Every identity configuration specifies an `identity_id`, target `renderer_id`, `voice_configuration`, and `provenance`.
4. Composite voice blending and embedding configurations remain omitted until V1.

## Consequences
- Clean separation between identity definitions and runtime capability execution.
- Switching or adding voice personas requires only creating a new config file.
- Identity format is forwards-compatible with composite provenance metadata.

## Status
Accepted