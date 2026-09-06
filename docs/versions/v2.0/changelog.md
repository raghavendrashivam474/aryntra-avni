# Aryntra Avni V2.0 Changelog

All notable changes introduced during the V2.0 Real-World Voice Identity Validation.

## [2.0.0] — 2026-09-06

### Added
- **Real-Speech Evaluation Harness (experiments/voice/v2_0_harness.py):** Reproducible, standardized experiment architecture designed to evaluate voice representations on real speech.
- **Evaluation Pipeline Script (experiments/voice/v2_0_eval.py):** Automated orchestration of enrollment, profile persistence, capability routing, generation, and multi-dimensional similarity testing.
- **Evaluation Metrics Report (experiments/voice/v2_0_analysis.py):** Structured generator producing comprehensive visual markdown reports of the identity transfer metrics.
- **Human Subjective listening protocol (experiments/voice/v2_0_human_eval.py):** Subjective assessment tool tracking perceptual naturalness (MOS) and identification accuracy.
- **Harness Verification Suite (	ests/experiments/test_v2_0_evaluation.py):** Unit and integration testing verifying resampling, hashing, metadata extraction, and config bindings.

### Changed
- **Zero modification to Core production codebase:** Preserved the robust V1.5.0 baseline completely untouched.
