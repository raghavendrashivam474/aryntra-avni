# Changelog — Aryntra Avni V1.0

All notable changes in **Aryntra Avni V1.0 (Reusable Voice Identity Foundation)** are documented here.

## [1.0.0] — 2026-05-09

### Added
- **Voice Enrollment Pipeline (src/enrollment/)**:
  - AudioSample, EnrollmentRequest, and EnrollmentResult immutable data contracts.
  - Strict audio validation (alidate_audio_file): WAV format checking, duration bounds (1.0s – 60.0s), minimum sample rate (16kHz), and channel limits.
  - Audio preprocessor (preprocess_audio): PCM decoding, sample rate normalization, and stereo-to-mono downmixing.
  - EnrollmentService: Invariant validation, preprocessing orchestration, and pluggable representation extraction.
- **Voice Representation Layer (src/representation/)**:
  - VoiceRepresentation immutable data contract with schema versioning and base64 serialization.
  - RepresentationExtractor abstract base class defining extract() and similarity() interfaces.
  - AcousticFeatureExtractor: Deterministic 8-dimensional normalized acoustic statistics vector (mean amplitude, standard deviation, zero-crossing rate, RMS energy, normalized spectral centroid, low/mid/high frequency energy ratios) in pure Python without heavy ML/C++ dependencies.
- **Persistent Profile Management & Consent (src/profiles/)**:
  - ConsentRecord and ConsentStatus (ACTIVE, REVOKED, EXPIRED) for explicit authorization tracking.
  - ProvenanceRecord for extraction lineage, sample count, and reproducible hashes.
  - VoiceIdentityProfile schema version 1.0 contract.
  - ProfileStore: Atomic filesystem persistence (data/profiles/), JSON serialization, profile validation, and lookup.
- **Capability Resolution (src/capabilities/voice/)**:
  - VoiceCapability resolves unknown identities dynamically from ProfileStore and auto-binds them to active TTS renderers.
  - IdentityLoader.load_from_profile() converts persistent profiles into synthesizable VoiceIdentity models.
  - create_default_voice_capability() factory automatically connects ProfileStore from data/profiles/.
- **Architectural Decision Records**:
  - ADR 0010: Voice Identity Primitive, Persistent Profiles, and Capability Resolution.
- **Evaluation & Benchmarks**:
  - experiments/voice/v1_eval.py benchmarking extraction determinism, speaker discriminability, and end-to-end lifecycle latency.
  - docs/evaluation/v1_results.md recording evaluation outcomes.

### Changed
- VoiceIdentity contract extended with optional epresentation_id and profile_id (100% backward compatible).
- Project version bumped to 1.0.0.
