# Aryntra Avni V2.0 Known Limitations

This document lists current technical boundaries identified during V2.0 real-speech validation.

---

## 1. Semantic Embedding Model Mismatch

- **Limitation:** NeuralSpeakerExtractor extracts VoxCeleb-trained x-vectors via SpeechBrain. SpeechT5TTSAdapter expects SpeechT5-specific encoder embeddings.
- **Impact:** While both are 512-dimensional unit-sphere representations, their semantic features are not perfectly aligned.
- **Status:** Evaluated and found sufficient for coarse speaker identity separation, but limits optimal timbre transfer.

---

## 2. In-Memory Resampling and Preprocessing

- **Limitation:** The core enrollment preprocessor does not resample sample rates (S0 Finding 1). It has been temporarily mitigated at the experiment boundary.
- **Impact:** Real-world enrollment files of 44.1kHz or 48kHz must be resampled to 16kHz before hitting the core pipeline.
- **Resolution:** Proposed for core implementation in V2.5.

---

## 3. High Initial Model Initialization Latency

- **Limitation:** Loading PyTorch, transformers, SpeechBrain, and SpeechT5 onto CPU takes ~17.2 seconds on first execution.
- **Impact:** Initial request latency is high, though subsequent generation runs drop to ~2-3 seconds.
- **Status:** Out of scope for V2.0.
