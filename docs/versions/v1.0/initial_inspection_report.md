# V1.0 Initial Inspection Report

**Date:** 2025-09-05
**Baseline:** v0.5.0 (commit b3411e5)
**Branch:** v1.0-voice-identity
**Status:** Inspection complete. No production code modified during inspection.

---

## 1. Current Repository State

- Clean working tree on v1.0-voice-identity (branched from v0.5.0)
- Tags: v0.1.0, v0.5.0
- Linear history, 12 commits
- Python 3.13, dependencies: edge-tts>=7.2.8, piper-tts>=1.8.0
- Local Piper model: models/voices/en_US-lessac-medium.onnx

## 2. Existing Components

### Contracts (src/contracts/)
- voice.py: VoiceRequest, VoiceResponse, VoiceIdentity (frozen dataclasses)
- renderer.py: TTSRenderer ABC, RenderResult
- errors.py: AvniVoiceError, VoiceErrorCode enum

### Capabilities (src/capabilities/voice/)
- capability.py: VoiceCapability orchestrator (validate→resolve→render→fallback→respond)
- registry.py: IdentityRegistry, RendererRegistry (in-memory dicts)
- identity_loader.py: IdentityLoader (JSON→VoiceIdentity)
- __init__.py: create_default_voice_capability() factory

### Adapters (src/adapters/tts/)
- edge_tts_adapter.py: EdgeTTSAdapter (renderer_id="edge_tts")
- piper_adapter.py: PiperTTSAdapter (renderer_id="piper")

### Identity Configs (configs/identities/)
- avni_default.json: edge_tts primary, piper fallback
- avni_guy.json: edge_tts only
- avni_offline.json: piper only

## 3. Key Architectural Observations

1. VoiceIdentity is a **declarative renderer mapping**, not a learned voice representation.
   It maps identity_id → renderer_id + voice_configuration dict.
2. No voice representation/embedding exists anywhere in V0.5.
3. Neither Edge-TTS nor Piper supports runtime speaker conditioning.
4. NAV integration is clean: VoiceRequest(text, identity_id) → VoiceResponse.
5. Fallback policy lives in VoiceCapability, not in adapters. Correct.

## 4. Reusable vs. Gap Analysis

**Reusable as-is:** All contracts, registries, adapters, fallback, NAV boundary.
**Gaps for V1:** Enrollment pipeline, representation abstraction, persistent profiles,
consent metadata, evaluation framework.

## 5. Key Decision: Representation Strategy

Neither existing renderer can consume a custom embedding. V1 will:
- Establish the identity primitive (enroll → represent → persist → resolve)
- Use a lightweight acoustic-feature representation (no heavy ML deps)
- Document the synthesis integration gap honestly
- Leave the representation boundary replaceable for future ML-based renderers

## 6. Sprint Sequence

S1→Enrollment | S2→Representation | S3→Persistence | S4→Integration | S5→Evaluation
