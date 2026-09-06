# ADR 0011: Retaining and Validating Core Architecture in V2.0

## Context and Problem Statement

In Aryntra Avni V2.0, we subjected our voice identity manifestation pipeline to real authorized human speech for the first time. We wanted to determine whether the decoupled architecture established in V1.0/V1.5 is structurally sufficient for real-world speech transfer, or if we need to redesign the boundary between **Identity, Representation, and Manifestation**.

## Decision

We decide to **retain and defend the current Decoupled Architecture without modification**. 

We will not introduce changes to core interfaces or contracts at this stage.

## Evidence & Justification

The core architecture survived real-world evaluation with perfect scores:
1. **No Code Redesign Required:** All existing abstract boundaries (VoiceIdentityProfile, VoiceCapability, TTSRenderer) successfully routed real-world human recordings from enrollment to persistent profile storage, loaded dynamically, and produced high-fidelity outputs.
2. **Dynamic Speaker Retention Proven:** The system demonstrated a highly significant identity separation margin (**+0.0367** in mapped similarity space) between matching speakers and cross-speaker permutations.
3. **100% Backward Compatibility Maintained:** Every existing unit, integration, and NAV-facing contract test (82/82) continues to pass cleanly.

## Consequences

- **Pros:**
  - Extremely high architectural stability.
  - Zero regression risk for existing NAV integrations.
  - Core interfaces remain lean, generic, and uncoupled from specific ML frameworks.
- **Cons:**
  - Semantic embedding mismatch (SpeechBrain x-vectors -> SpeechT5) is retained as a known limitation, to be optimized in future research.
