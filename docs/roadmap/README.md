# Aryntra Avni — Roadmap

## Milestone Overview

`	ext
V0   — Voice Foundation (Completed)
V0.5 — Voice Identity Baseline & Offline Fallback (Completed)
V1   — Composite Voice Identity (Multi-source)
V1.5 — Dynamic Composition & Contextual Blending
V2   — Expressive Identity
V3   — Adaptive Identity
V4+  — Multimodal Synthetic Identity
Milestone Status
V0 — Voice Foundation (Completed — Tag: v0.1.0)
 Establish consumer boundary & contracts (VoiceRequest, VoiceResponse)
 Isolate TTS execution behind adapter interface (TTSRenderer)
 Provide baseline identity representation (VoiceIdentity)
 Enable clean in-process NAV integration
 Initial benchmark and contract test coverage
V0.5 — Voice Identity Baseline & Offline Fallback (Completed — V0.5.0)
 Implement local offline neural TTS adapter (PiperTTSAdapter via ONNX)
 Establish identity-aware fallback policy across cloud and local engines
 Add offline voice persona configuration (avni_offline.json)
 Comprehensive audio validation (WAV/RIFF, MP3 frame checking)
 Expanded benchmark suite (>= 50 invocations measuring p50, p95, p99, and cold start)
 Zero-breaking-change NAV integration preservation
V1 — Composite Voice Identity (Upcoming Scope)
 Multi-source vocal identity definitions
 Static speaker interpolation / composite voice models
 Provenance attribution for composite sources
 Custom speaker embeddings and parameter blending
Explicit Non-Goals for V0.5 (Deferred to V1+)
Multi-speaker voice blending / interpolation
Dynamic speaker embedding research
Voice cloning from arbitrary audio samples
Distributed microservice infrastructure
Multimodal / behavioral modeling