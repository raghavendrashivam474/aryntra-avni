# V2.0 Initial Inspection Report

**Date:** 2026-09-06
**Baseline:** V1.5.0 (commit 6ffdcbf)
**Branch:** feat/v2.0-real-world-validation
**Test baseline:** 74/74 passing

---

## 1. Files Inspected

| # | File | Status |
|---|------|--------|
| 1 | `src/contracts/voice.py` | Reviewed |
| 2 | `src/representation/base.py` | Reviewed |
| 3 | `src/representation/neural_extractor.py` | Reviewed |
| 4 | `src/profiles/voice_profile.py` | Reviewed |
| 5 | `src/profiles/profile_store.py` | Reviewed |
| 6 | `src/capabilities/voice/identity_loader.py` | Reviewed |
| 7 | `src/capabilities/voice/capability.py` | Reviewed |
| 8 | `src/adapters/tts/speecht5_adapter.py` | Reviewed |
| 9 | `src/enrollment/enrollment_service.py` | Reviewed |
| 10 | `src/enrollment/contracts.py` | Reviewed |
| 11 | `src/enrollment/preprocessor.py` | Reviewed |
| 12 | `src/enrollment/audio_validator.py` | Reviewed |
| 13 | `src/contracts/errors.py` | Reviewed |
| 14 | `src/contracts/renderer.py` | Reviewed |
| 15 | `src/representation/acoustic_extractor.py` | Reviewed |
| 16 | `src/profiles/consent.py` | Reviewed |
| 17 | `tests/integration/test_v1_5_neural_synthesis.py` | Reviewed |
| 18 | `tests/representation/test_neural_extractor.py` | Reviewed |
| 19 | `tests/adapters/test_speecht5_adapter.py` | Reviewed |

---

## 2. Architecture Assessment

### Invariants Confirmed Intact

| Invariant | Status | Notes |
|-----------|--------|-------|
| Voice Identity != Renderer | PASS | VoiceIdentity is renderer-agnostic; renderer_id is a binding |
| Kernel knows concepts; plugins know technologies | PASS | No ML imports in contracts, profiles, or capability |
| Capability owns policy | PASS | Adapters receive voice_config dict, never touch ProfileStore |
| Representation remains an abstraction | PASS | RepresentationExtractor ABC; x-vector is one implementation |
| Consent and provenance first-class | PASS | ConsentRecord + ProvenanceRecord in every profile |
| NAV-facing contracts stable | PASS | VoiceRequest/VoiceResponse unchanged |

### Data Flow Verified
Audio -> EnrollmentService -> NeuralSpeakerExtractor -> VoiceRepresentation
-> VoiceIdentityProfile -> ProfileStore (JSON, atomic write)
-> IdentityLoader.load_from_profile() -> VoiceIdentity (with representation_data)
-> VoiceCapability.synthesize() -> SpeechT5TTSAdapter.render() -> WAV


---

## 3. Critical Findings

### Finding 1: Preprocessor Does Not Resample (MEDIUM RISK)

**File:** `src/enrollment/preprocessor.py`

The preprocessor converts stereo to mono but does **not** resample to 16kHz.
If the input already matches target format, it returns raw file bytes unchanged.

**Impact on V2.0:** Real human recordings are commonly 44.1kHz or 48kHz.
The neural extractor's `_read_wav_samples` reads at native rate and feeds
directly to SpeechBrain, which expects 16kHz input. This will produce
**incorrect embeddings** for non-16kHz recordings.

**V2.0 approach:** Handle resampling at the experiment boundary (not modifying
core preprocessor) until evidence shows this is a systemic problem.

### Finding 2: Embedding Model Mismatch (HIGH RISK — Core Research Question)

**Files:** `neural_extractor.py`, `speecht5_adapter.py`

- NeuralSpeakerExtractor uses **SpeechBrain VoxCeleb x-vector** (512-dim)
- SpeechT5TTSAdapter was trained with **SpeechT5's own speaker encoder** (512-dim)

These are **different models** trained on **different data** with **different
objectives**. They are dimensionally compatible (both 512-dim float32) but
**semantically mismatched**.

This is the fundamental research question V2.0 must answer:
> Does an x-vector from SpeechBrain produce meaningful speaker conditioning
> when fed to SpeechT5's decoder?

### Finding 3: Similarity Mapping (LOW RISK — Informational)

**File:** `neural_extractor.py`, line: `return float(max(0.0, min(1.0, (sim + 1.0) / 2.0)))`

Cosine similarity [-1, 1] is mapped to [0, 1]. This means unrelated speakers
score ~0.5, not ~0.0. V2.0 analysis must account for this when interpreting
cross-speaker separation numbers.

### Finding 4: V1.5 Evaluation Used Synthetic Tones (EXPECTED)

**File:** `tests/integration/test_v1_5_neural_synthesis.py`

The existing test creates sine waves at 110Hz and 250Hz. This validates the
plumbing but cannot demonstrate real voice identity. V2.0 closes this gap.

---

## 4. Compatibility Assessment

| Component | V2.0 Compatible? | Notes |
|-----------|-----------------|-------|
| VoiceRequest/VoiceResponse | Yes | No changes needed |
| VoiceIdentity | Yes | representation_data flows through voice_configuration |
| RepresentationExtractor ABC | Yes | NeuralSpeakerExtractor implements it correctly |
| VoiceRepresentation | Yes | 512-dim float32 bytes, base64 in profile |
| VoiceIdentityProfile | Yes | Schema 1.0, roundtrip tested |
| ProfileStore | Yes | Atomic JSON, sanitized paths |
| IdentityLoader | Yes | Routes neural_xvector to speecht5 |
| VoiceCapability | Yes | Resolves from ProfileStore, fallback intact |
| SpeechT5TTSAdapter | Yes | Accepts 512-dim bytes, outputs 16kHz WAV |
| EnrollmentService | Yes | Validates, preprocesses, extracts |
| AudioValidator | Yes | WAV, >=16kHz, 1-60s |
| Preprocessor | Partial | No resampling (see Finding 1) |

---

## 5. Proposed V2.0 Implementation Boundary

### New files (experiment layer only):
- `experiments/voice/v2_0_harness.py` — Evaluation harness utilities
- `experiments/voice/v2_0_eval.py` — Main evaluation script
- `experiments/voice/v2_0_analysis.py` — Metrics and reporting
- `experiments/voice/v2_0_human_eval.py` — Human listening protocol
- `tests/experiments/test_v2_0_evaluation.py` — Harness unit tests
- `docs/versions/v2.0/*` — Documentation
- `docs/evaluation/v2_0_results.md` — Results
- `data/evaluation/` — Authorized audio (gitignored)

### Existing files modified: **NONE** (until S7 evidence review)

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Embedding mismatch produces poor conditioning | High | High | This IS the research question; measure it |
| Non-16kHz recordings produce bad embeddings | Medium | High | Resample at experiment boundary |
| SpeechT5 naturalness too poor for identity judgment | Medium | Medium | Document; separate naturalness from identity |
| Insufficient authorized speakers available | Low | High | Minimum 2 speakers; use what is available |
| Model download failures in CI | Low | Medium | Cache models; document requirements |

---

## 7. Next Steps

1. Build evaluation harness (S1)
2. Prepare authorized human speech dataset (S2)
3. Run representation-level experiments (S3)
4. Run end-to-end identity experiments (S3)
5. Human listening evaluation (S5)
6. Evidence review and architecture decision (S6-S7)
