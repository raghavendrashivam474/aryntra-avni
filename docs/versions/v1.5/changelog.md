# V1.5 Changelog

## [1.5.0] — 2026-09-05

### Added
- **Neural Speaker Representation Extractor** (`NeuralSpeakerExtractor`): Implemented deep speaker neural embedding extraction extracting 512-dimensional x-vector vectors using `speechbrain/spkrec-xvect-voxceleb`.
- **Speaker-Conditioned TTS Adapter** (`SpeechT5TTSAdapter`): Implemented dynamic runtime speaker-conditioned speech generation using Microsoft SpeechT5 and HiFi-GAN vocoders.
- **Unified Unit Testing**:
  - `tests/representation/test_neural_extractor.py` for encoder testing.
  - `tests/adapters/test_speecht5_adapter.py` for adapter contract verification.
- **End-to-End Life-cycle Tests**: Integrated `tests/integration/test_v1_5_neural_synthesis.py` to evaluate complete enrollment, persistence, clearing, resolution, and conditioned manifestation.
- **Formal Evaluation Script**: Created `experiments/voice/v1_5_eval.py` to compile mathematical verification reports on determinism, identity retention, and cross-speaker separation.

### Changed
- **Identity Loader Enhancement**: Updated `IdentityLoader.load_from_profile` to bind the raw profile `representation.data` bytes into `voice_configuration["representation_data"]` for consumption by conditioned neural adapters.
- **Registry Injection**: Configured `create_default_voice_capability` to pre-register the `SpeechT5TTSAdapter` alongside standard baseline renderers.

### Fixed
- Fixed runtime routing to default neural profiles directly to `"speecht5"` if their representation metadata contains `"neural_xvector"`.
