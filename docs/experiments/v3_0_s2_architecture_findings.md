# Avni V3.0 S2 — Architecture Findings

## 1. Overview of Identity & Expression Flows
As established by S1, Avni separates persistent synthetic identity representation from expression inputs. The identity profile represents a stable voice signature extracted from authorized speech. The ExpressionConfig (pitch, rate, and energy scales) is injected only at request execution time.

## 2. Component Interrogation
* **Contracts (src/contracts/)**: Stable structures (VoiceRequest, VoiceResponse, ExpressionConfig). No expansion is authorized.
* **Identity Loader (src/capabilities/voice/identity_loader.py)**: Responsible for mapping serialized profiles to live VoiceIdentity configurations.
* **Renderer Mapping**:
  * Neural representation: Uses acoustic/neural embedding metrics.
  * Manifestation path: Currently routes request-scoped context to TTS and Voice Conversion adapters.

## 3. Current S1 Test Baseline
* **Immutability Verified**: 	est_expression_does_not_mutate_voice_identity guarantees that requests carrying variations do not modify the persistent storage metrics.
* **Evaluation Scope**: Prior benchmarks relied on deterministic synthetic and randomized mock arrays.

## 4. Architectural Risks & Known Coupling
* **Rate-Pitch Coupling**: The underlying post-processing algorithms (e.g., SpeechT5 post-processing) may introduce unintentional pitch drift when speed rate is shifted. This coupling will be quantified experimentally.
* **Extraction Boundary**: If voice profiles fail to match across expressive ranges, we must define whether it is a limitation of the embedding model, or if the synthesis architecture degrades identity features.
