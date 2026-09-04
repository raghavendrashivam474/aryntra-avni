# ADR 0003: Voice Capability Boundary and Contract Design

## Context
V0 requires a stable interface between NAV and Avni's voice capability that
is completely decoupled from any specific TTS engine.

## Existing Approach
None — this is the first implementation.

## Decision
1. `VoiceRequest` / `VoiceResponse` are frozen dataclasses with only fields
   that serve a current purpose (Section 5 of the brief).
2. `AvniVoiceError` + `VoiceErrorCode` enum standardise all domain failures.
   Raw engine exceptions are caught and wrapped — never leaked.
3. `TTSRenderer` (ABC) defines the adapter boundary.  Concrete engines live
   in `src/adapters/tts/` and are the only files that import vendor SDKs.
4. `VoiceCapability.synthesize()` orchestrates validate → resolve → invoke.
5. Registries are in-memory for V0.  No database, no config server.

## Rationale
- Zero third-party dependencies in the core contract layer.
- Renderer swap requires only a new adapter class + registry call.
- Frozen dataclasses prevent accidental mutation across the boundary.

## Consequences
- **Positive:** NAV has a clean, testable API.  Renderer tech is fully hidden.
- **Trade-off:** In-memory registries mean identities are configured in code
  or loaded at startup — acceptable for V0, revisit at V0.5.

## Status
Accepted