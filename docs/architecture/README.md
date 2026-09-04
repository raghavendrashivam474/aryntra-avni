# Aryntra Avni — Architecture

## 1. Architectural Boundary

Avni sits between consumers (such as NAV) and underlying rendering technologies (TTS engines).

```text
                         NAV
                          │
                          │ Voice Request
                          ▼
                    ┌───────────┐
                    │   Avni    │
                    │ Voice API │
                    └─────┬─────┘
                          │
                    Voice Identity
                          │
                    Renderer Contract
                          │
                    TTS Adapter
                          │
                          ▼
                        Audio

Core Invariant: NAV must depend exclusively on Avni's voice capability contract, never directly on a specific TTS engine or SDK.

## 2. Conceptual Separation: Identity vs Renderer
```text
Voice Identity (What/Who speaks)
       │
       ▼
Renderer Configuration (How the identity maps to parameters)
       │
       ▼
TTS Adapter (Bridge to engine)
       │
       ▼
TTS Engine (Execution)
```

## 3. Repository Directory Responsibilities
```text 
artifacts/: Generated evaluation audio, test artifacts, metrics outputs.
configs/: Identity configurations, renderer configurations, environment profiles.
data/: Raw source audio and processed data for future identity research.
docs/: Vision, architecture, roadmap, evaluation, experiments, and ADRs.
experiments/: Research scripts, evaluation benchmarks, exploratory prototypes.
scripts/: Operational scripts and verification entrypoints.
src/contracts/: Technology-agnostic domain contracts (requests, responses, errors, interfaces).
src/capabilities/: Core capability orchestrators (e.g. VoiceCapability) and registries.
src/adapters/: Concrete integrations bridging contracts/ to specific external engines.
src/core/: Common utilities, logging, configuration helpers.
tests/: Contract tests, unit tests, adapter smoke tests, integration tests.
```