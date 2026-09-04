# Aryntra Avni — V0 Known Limitations

**Version:** V0 — Voice Foundation
**Audience:** NAV developers, Avni contributors, future milestone planners

---

## 1. Purpose of This Document

This document explicitly lists what V0 does **not** do. These are not bugs or oversights. They are intentional deferrals documented to prevent confusion and scope creep in future milestones.

---

## 2. Identity Limitations

### 2.1 Static Identity Only
V0 identities are static JSON configurations mapping an `identity_id` to a single renderer and a single voice. There is no:
- Composite voice blending (e.g., Human A + Human B → Avni)
- Dynamic interpolation (e.g., 70% A + 30% B based on context)
- Speaker embedding generation or manipulation
- Voice cloning from audio samples
- Multi-source identity composition

**Deferred to:** V1 (Composite Voice Identity), V1.5 (Dynamic Composition)

### 2.2 No Expressive Control
V0 does not expose expressive parameters such as:
- Warmth, energy, seriousness, urgency
- Emotional tone modulation
- Prosodic variation beyond rate/pitch

The underlying Edge-TTS engine supports `rate` and `pitch` in voice configs, which are exposed as static configuration values. Dynamic expressive control is not implemented.

**Deferred to:** V2 (Expressive Identity)

### 2.3 No Adaptive Behavior
V0 identities do not adapt based on:
- Audience characteristics
- Environmental context
- Conversation state
- Time of day or user preference

**Deferred to:** V3 (Adaptive Identity)

---

## 3. Renderer Limitations

### 3.1 Single Active Renderer
V0 ships with one renderer adapter: `EdgeTTSAdapter`. While the architecture supports multiple renderers via the `TTSRenderer` interface and `RendererRegistry`, only one is registered by default.

### 3.2 Network Dependency
The default Edge-TTS renderer requires internet access. There is no offline fallback in V0. If the network is unavailable, synthesis will fail with `RENDERER_UNAVAILABLE` or `GENERATION_FAILURE`.

**Mitigation path:** V0.5 can introduce a local renderer adapter (e.g., Piper ONNX) as a fallback.

### 3.3 No Streaming
`VoiceRequest.streaming` exists as a field but is not implemented. All synthesis is batch (full audio returned at once). Streaming support requires renderer-level changes.

**Deferred to:** Post-V0, when a streaming consumer requirement emerges.

---

## 4. Integration Limitations

### 4.1 In-Process Only
V0 integration is strictly in-process Python. There is no:
- HTTP API server
- gRPC service
- Message queue integration
- WebSocket streaming endpoint

NAV must import Avni as a Python library. This is intentional (ADR 0006) to avoid premature infrastructure.

**Revisit when:** NAV requires out-of-process or cross-language integration.

### 4.2 In-Memory Registries
Identity and renderer registries are in-memory dictionaries. They are populated at startup from JSON files. There is no:
- Database persistence
- Hot-reloading of identity configs
- Remote identity registry
- Identity versioning

**Revisit at:** V0.5 or when identity count grows significantly.

---

## 5. Quality Limitations

### 5.1 No Automated Audio Quality Scoring
V0 evaluation relies on:
- Byte-level integrity checks (audio size > threshold)
- Latency measurement
- Success/failure rate

There is no automated MOS (Mean Opinion Score), PESQ, or STOI measurement. Naturalness assessment is currently manual/subjective.

### 5.2 Limited Benchmark Scope
The V0 benchmark runs 9 invocations across 3 phrases. This is sufficient for baseline verification but not for production-grade load testing or stress evaluation.

---

## 6. What to Do If You Hit a Limitation

1. **Check if it's already planned:** Review `docs/roadmap/README.md` for the target milestone.
2. **Check if it's a V0 bug vs. a V0 limitation:** If the behavior contradicts this document or the ADRs, file it as a bug. If it matches this document, it's a known deferral.
3. **Propose acceleration:** If NAV has an urgent need for a deferred capability, propose a milestone re-prioritization with a clear justification. Do not implement it ad-hoc.

---

## 7. Summary Table

| Capability | V0 Status | Target Milestone |
|-----------|-----------|-----------------|
| Single static voice identity | ✅ Implemented | V0 |
| Multiple static identities | ✅ Implemented | V0 |
| Composite voice blending | ❌ Deferred | V1 |
| Dynamic context interpolation | ❌ Deferred | V1.5 |
| Expressive parameter control | ❌ Deferred | V2 |
| Adaptive identity behavior | ❌ Deferred | V3 |
| Offline/local rendering | ❌ Deferred | V0.5 |
| Streaming synthesis | ❌ Deferred | Post-V0 |
| Network API (HTTP/gRPC) | ❌ Deferred | When required |
| Voice cloning / embeddings | ❌ Deferred | V1+ |
| Multimodal identity | ❌ Deferred | V4+ |