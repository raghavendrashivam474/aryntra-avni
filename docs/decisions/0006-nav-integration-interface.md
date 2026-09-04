# ADR 0006: NAV Integration Boundary and Entrypoint

## Context
NAV requires a simple, direct interface to synthesize speech using Avni identities without needing to initialize adapters, understand config file paths, or manage registries.

## Decision
1. Provide `create_default_voice_capability()` as the recommended in-process factory.
2. Expose standard high-level contracts (`VoiceRequest`, `VoiceResponse`, `AvniVoiceError`) at the top-level `src` namespace.
3. Keep the integration strictly in-process Python for V0 (no HTTP / gRPC / microservices).

## Consequences
- Single-line initialization for NAV: `voice = create_default_voice_capability()`.
- Complete isolation of adapters and config paths from NAV.
- Zero network latency overhead during V0 development.

## Status
Accepted