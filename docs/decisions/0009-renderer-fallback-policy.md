# ADR 0009: Identity-Aware Renderer Fallback Policy

## Context
V0.5 introduces offline synthesis via Piper ONNX. When a cloud-backed voice identity (e.g., edge_tts) experiences network loss or engine failure, NAV should seamlessly receive speech synthesized via a local offline fallback renderer without breaking the public contract.

## Alternatives Considered
1. **Adapter-Internal Fallback**: EdgeTTSAdapter internally calls PiperTTSAdapter.
   - *Rejected*: Violates single responsibility; couples cloud adapter to local engine.
2. **Blind Global Fallback**: VoiceCapability falls back to a hardcoded local engine whenever any renderer fails.
   - *Rejected*: Fails identity fidelity. Different personas require different offline surrogate voices.
3. **Identity-Aware Fallback in Capability Layer**: VoiceIdentity optionally declares allback_renderer_id and allback_voice_configuration. VoiceCapability orchestrates fallback explicitly.
   - *Accepted*: Clean separation of concerns, persona-specific fallback parameters, full observability.

## Decision
1. Extend VoiceIdentity with optional fields:
   - allback_renderer_id: Optional[str] = None
   - allback_voice_configuration: Dict[str, Any] = field(default_factory=dict)
2. IdentityLoader parses these optional fallback fields from identity JSON files.
3. VoiceCapability.synthesize() implements explicit fallback execution:
   - Primary renderer is resolved and invoked.
   - If primary renderer is unavailable or fails with AvniVoiceError, and allback_renderer_id is defined and registered, fallback is attempted.
   - If fallback succeeds, VoiceResponse.metadata records allback_used = True, primary_renderer_id, enderer_id, and allback_latency_sec.
   - If fallback also fails, the original error and fallback error are reported.
4. create_default_voice_capability() pre-registers both EdgeTTSAdapter and PiperTTSAdapter.

## Consequences
- **Positive**: Complete offline resilience for NAV without changing the public calling convention.
- **Positive**: 100% backward-compatible: identities without fallback fields function identically to V0.
- **Positive**: Full observability through structured metadata and logging.

## Status
Accepted