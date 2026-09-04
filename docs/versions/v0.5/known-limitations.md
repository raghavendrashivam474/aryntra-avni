# Known Limitations — Aryntra Avni V0.5

This document details known technical limitations, architectural trade-offs, and operational constraints in **Aryntra Avni V0.5**.

---

## 1. Local Renderer Cold Start Latency
- **Limitation**: The first synthesis invocation using PiperTTSAdapter takes ~4.2s.
- **Root Cause**: ONNX Runtime initializes the inference session and loads model graph weights into memory on first access.
- **Mitigation in V0.5**: The adapter caches loaded PiperVoice instances in _loaded_voices. Subsequent invocations execute in **~80–320ms**.
- **Future Resolution (V1)**: Implement optional background pre-warming of default offline models during create_default_voice_capability().

---

## 2. Voice Persona Timbre Gap on Fallback
- **Limitation**: When vni_default falls back from cloud (en-US-AriaNeural) to local (en_US-lessac-medium), the speaker's vocal characteristics and timbre differ noticeably.
- **Architectural Trade-off**: Fallback in V0.5 is designed as a *resilience mechanism* (ensuring speech is produced when the network is down), not an identical voice clone.
- **Mitigation in V0.5**: Response metadata records allback_used: True, primary_renderer_id: "edge_tts", and enderer_id: "piper" for full transparency.
- **Future Resolution (V1+)**: Investigate custom speaker fine-tuning or voice conversion to match local surrogate voices to cloud personas.

---

## 3. Synchronous Caller Assumption in Edge-TTS
- **Limitation**: EdgeTTSAdapter utilizes syncio.run() internally to interface with the async edge-tts library. Calling synthesize() from within an active, running event loop (e.g. FastAPI / async framework) will raise RuntimeError.
- **Status**: Documented in ADR 0007; acceptable for current synchronous NAV integration.
- **Future Resolution**: Introduce native asynchronous capability interface (synthesize_async()) when NAV requires async invocation.

---

## 4. Manual Model Asset Distribution
- **Limitation**: ONNX model binary files (~60MB) are excluded from git via .gitignore to prevent repository bloat. New environments must download the .onnx and .onnx.json files.
- **Mitigation in V0.5**: Download paths and instructions are documented in the completion report and benchmark scripts.
- **Future Resolution (V1)**: Implement an automated model artifact downloader utility (scripts/setup_models.py) with checksum verification.

---

## 5. In-Memory Registry Lifecycle
- **Limitation**: IdentityRegistry and RendererRegistry operate strictly in-memory during the application process lifecycle. Dynamic identity updates made at runtime are not persisted back to disk.
- **Status**: Acceptable for V0.5 per ADR 0003 and ADR 0005. Identity configuration files in configs/identities/ remain the single source of truth.
- **Future Resolution**: No distributed database needed until multi-node deployment requirements emerge.

---

## 6. Scope Boundaries Maintained (Non-Goals)
The following capabilities remain deliberately deferred to future milestones:
- Multi-source composite voice blending (deferred to V1).
- Dynamic vocal interpolation / weighting (deferred to V1.5).
- Expressive tone and emotion modulation (deferred to V2).
- Real-time audio stream chunking (deferred until explicit streaming requirements emerge).