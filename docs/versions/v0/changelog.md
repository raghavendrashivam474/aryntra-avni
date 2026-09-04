# Aryntra Avni — V0 Changelog

**Version:** V0 — Voice Foundation
**Baseline:** Empty repository (skeleton directory structure only)

---

## V0 (Initial Release)

### Added

**Core Contracts (`src/contracts/`)**
- `VoiceRequest` — Frozen dataclass for synthesis requests (text, identity_id, context)
- `VoiceResponse` — Frozen dataclass for synthesis results (audio_bytes, format, metadata)
- `VoiceIdentity` — Frozen dataclass for identity representation (identity_id, renderer_id, voice_configuration, provenance)
- `TTSRenderer` — Abstract base class defining the renderer adapter interface
- `RenderResult` — Dataclass for raw adapter output
- `AvniVoiceError` — Structured domain exception with `VoiceErrorCode` enum
- `VoiceErrorCode` — Enum covering INVALID_REQUEST, UNKNOWN_IDENTITY, RENDERER_UNAVAILABLE, GENERATION_FAILURE, CONFIGURATION_FAILURE, TIMEOUT

**Capability Layer (`src/capabilities/voice/`)**
- `VoiceCapability` — Main orchestrator (validate → resolve identity → resolve renderer → invoke → respond)
- `IdentityRegistry` — In-memory identity lookup with structured error handling
- `RendererRegistry` — In-memory renderer lookup with availability checking
- `IdentityLoader` — JSON config loader with UTF-8 BOM resilience and validation
- `create_default_voice_capability()` — Factory function for one-line NAV initialization

**Renderer Adapter (`src/adapters/tts/`)**
- `EdgeTTSAdapter` — Concrete TTS adapter using Microsoft Edge neural voices
- Clean async event loop handling compatible with Python 3.10+
- Full error wrapping (no raw `edge_tts` exceptions leak to consumers)

**Configuration (`configs/identities/`)**
- `avni_default.json` — Default identity (en-US-AriaNeural)
- `avni_guy.json` — Alternate identity (en-US-GuyNeural)

**Tests (`tests/`)**
- 8 contract tests (FakeRenderer, all error codes, happy path)
- 2 adapter tests (availability check, live synthesis smoke)
- 3 identity loader tests (directory loading, validation, missing file)
- 3 integration tests (NAV consumption flow, identity switching, error propagation)
- Total: 16 tests, 100% pass rate

**Evaluation (`experiments/voice/`)**
- `v0_eval.py` — Automated latency and reliability benchmark suite
- Results: 100% success rate, ~0.99s median warm latency

**Scripts (`scripts/`)**
- `nav_speak_example.py` — End-to-end NAV integration demonstration

**Documentation (`docs/`)**
- Vision, architecture, and roadmap documents
- 6 Architecture Decision Records (ADRs 0001–0006)
- V0 evaluation results report
- Comprehensive project README
- V0 completion report, known limitations, and this changelog

### Changed
- Nothing (initial release from empty skeleton)

### Deprecated
- Nothing

### Removed
- Nothing

### Fixed
- Nothing

---

## Pre-V0 State

The repository contained only an empty directory skeleton:

artifacts/, configs/, data/, docs/, experiments/, scripts/, src/, tests/
---
```text 
All directories were empty. No source code, no configuration, no documentation content.
```