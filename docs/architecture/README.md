# Aryntra Avni — Architecture

## 1. Architectural Boundary

Avni sits between consumers (such as NAV) and underlying rendering technologies (cloud and local TTS engines).

`	ext
                         NAV
                          │
                          │ Voice Request
                          ▼
                    ┌───────────┐
                    │   Avni    │
                    │ Voice API │
                    └─────┬─────┘
                          │
                    Voice Identity (with Fallback Policy)
                          │
                    Renderer Contract (TTSRenderer)
                          │
               ┌──────────┴──────────┐
               ▼                     ▼
          Cloud Adapter         Local Adapter
         (EdgeTTSAdapter)      (PiperTTSAdapter)
               │                     │
               └──────────┬──────────┘
                          ▼
                        Audio
Core Invariant: NAV must depend exclusively on Avni's voice capability contract (VoiceCapability, VoiceRequest, VoiceResponse), never directly on any specific TTS engine, SDK, or fallback implementation detail.

2. Conceptual Separation: Identity vs Renderer
text

Voice Identity (What/Who speaks & Fallback targets)
       │
       ▼
Renderer Configuration (How the identity maps to parameters)
       │
       ▼
TTS Adapter (Bridge to engine behind TTSRenderer)
       │
       ▼
TTS Engine (Execution: Edge-TTS cloud / Piper ONNX local)
3. Fallback Architecture (V0.5)
Identity-Aware: An identity defines its primary renderer_id and optional fallback_renderer_id.
Explicit Capability Orchestration: When a primary renderer fails (e.g. network timeout or service unavailability), VoiceCapability routes the request to the configured fallback renderer.
Observability: Fallback telemetry is captured in VoiceResponse.metadata (fallback_used, primary_renderer_id, renderer_id, generation_latency_sec).
4. Repository Structure
text

artifacts/        Generated audio outputs and test artifacts
configs/          Identity configurations (avni_default.json, avni_offline.json, avni_guy.json)
docs/             Architecture, decisions (ADRs 0001-0009), roadmap, and evaluation results
experiments/      Evaluation benchmarks (v0_5_eval.py)
models/           Local ONNX voice model binaries
scripts/          NAV demo execution scripts
src/
  ├── adapters/   TTS adapters (EdgeTTSAdapter, PiperTTSAdapter)
  ├── capabilities/ Voice capability orchestration and registries
  └── contracts/  Technology-agnostic domain contracts and error definitions
tests/            Contract, unit, adapter, fallback, and audio validation test suites