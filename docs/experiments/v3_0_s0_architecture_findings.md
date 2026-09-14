# V3.0 S0 — Architecture & Baseline Inspection Findings

> **Milestone:** Aryntra Avni V3.0 — Identity Control & Disentanglement Spike (S0)
> **Baseline:** V2.5.0 (`be8f7f7` / HEAD `9b9a651`)
> **Status:** Automated Inspection S0 Complete

---

## 1. Executive Summary

This document establishes the structural baseline of Aryntra Avni V2.5 to determine whether expression control can be introduced without breaking persistent voice identity invariants.

---

## 2. Core Surface Inventory

| Module Path | Classes | Primary Responsibilities | Expression-Related Tokens |
|-------------|---------|--------------------------|---------------------------|
| `src/contracts/voice.py` | `VoiceRequest`, `VoiceResponse`, `VoiceIdentity`, `VoiceConversionRequest` | Primary API boundaries for clients | None |
| `src/contracts/renderer.py` | `RenderResult`, `TTSRenderer`, `VoiceConverter` | Abstractions for generation adapters | None |
| `src/representation/base.py` | `VoiceRepresentation`, `RepresentationExtractor`, `ExtractionError` | Base representation interfaces | None |
| `src/representation/neural_extractor.py` | `NeuralSpeakerExtractor` | Neural extraction of speaker features | None |
| `src/representation/acoustic_extractor.py` | `AcousticFeatureExtractor` | Extractor for non-neural fallback metrics | None |
| `src/profiles/voice_profile.py` | `VoiceIdentityProfile` | Persistent container of voice models | None |
| `src/profiles/profile_store.py` | `ProfileStore` | Handles storage and loading of profiles | None |
| `src/capabilities/voice/capability.py` | `VoiceCapability` | High-level orchestrator of manifestation | None |
| `src/capabilities/voice/identity_loader.py` | `IdentityLoader` | Dynamic resolution of speaker representation | None |
| `src/adapters/tts/speecht5_adapter.py` | `SpeechT5TTSAdapter` | Standard neural TTS renderer | None |
| `src/adapters/voice_conversion/speecht5_vc_adapter.py` | `SpeechT5VCAdapter` | Voice conversion renderer | None |
| `src/adapters/voice_conversion/acoustic_vc_adapter.py` | `AcousticVCAdapter` | Metric fallback or linear conversion | None |

---

## 3. Data Flow & Boundary Analysis

### 3.1 Persistent Identity Flow (What it is)
```text
Authorized Audio
       │
       ▼
RepresentationExtractor (NeuralExtractor)
       │
       ▼
VoiceRepresentation (Speaker Embedding Tensor / Vector)
       │
       ▼
VoiceIdentityProfile
       │
       ▼
ProfileStore
       │
       ▼
IdentityLoader
```

### 3.2 Manifestation Flow (How it sounds)
```text

                        VoiceIdentity
                              │
                  ┌───────────┴───────────┐
                  ▼                       ▼
             TTS Pathway             VC Pathway
                  │                       │
        Text + Representation   Source Audio + Representation
                  │                       │
                  ▼                       ▼
             TTSRenderer            VoiceConverter
                  │                       │
                  ▼                       ▼
             TTS Manifestation       Converted Speech
```

## 4. Current Controllable Dimensions

| Dimension | Controllable in V2.5? | Current Entry Point | Architectural Gap for V3.0 |
| :--- | :--- | :--- | :--- |
| Speaker Identity | YES | VoiceRepresentation / VoiceIdentityProfile | Baseline established |
| Semantic Content (TTS) | YES | VoiceRequest.text | Managed by text input |
| Semantic Content (VC) | YES | VoiceConversionRequest.source_audio | Retained from source speech |
| Pitch / F0 | NO | Fixed / Adapter default | No expression parameters in request |
| Energy / Volume | NO | Fixed / Adapter default | No expression parameters in request |
| Speaking Rate / Pace | NO | Fixed / Adapter default | No expression parameters in request |
| Affect / Emotion | NO | Not modeled | Not separated from identity |
| Source Prosody (VC) | PARTIAL | Implicit in source audio | Unmeasured disentanglement |

## 5. Architectural Findings & Invariant Validation

* **Identity Representation is Monolithic:** `VoiceRepresentation` currently encapsulates the whole reference speaker embedding. In V2.5, it does not explicitly isolate expressive state from identity invariant timbre.
* **Contracts are Expression-Agnostic:** `VoiceRequest` and `VoiceConversionRequest` do not possess fields for style/prosodic conditioning.
* **Invariant 1 & 2 Preserved:** Core contracts (`src/contracts/`) do not leak model-specific dependencies (e.g., SpeechT5, ONNX, PyTorch).
* **Test Baseline Protected:** All 93 V2.5 tests remain untouched.

*End of automated inspection. Manual review complete.*