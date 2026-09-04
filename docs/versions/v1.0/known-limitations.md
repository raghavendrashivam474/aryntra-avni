# Known Limitations — Aryntra Avni V1.0

The following limitations are explicitly documented as architectural boundaries for V1.0:

1. **Acoustic Representation vs Neural Speaker Conditioning**:
   - V1.0 uses a statistical acoustic representation (AcousticFeatureExtractor, 8-dim normalized vector) for cross-platform zero-dependency extraction.
   - The current TTS renderers (Microsoft Edge-TTS and Piper ONNX) utilize fixed neural models and do not support dynamic runtime speaker conditioning vectors.
   - Therefore, synthesizing speech with a persistent profile currently routes through the configured renderer's neural voice while preserving identity metadata in the response. Full neural speaker cloning is scoped for future milestones (V2+).

2. **Single In-Process Storage**:
   - ProfileStore uses local filesystem JSON + base64 serialization. It is designed for single-node in-process usage and does not support distributed database sync or vector index searching.

3. **Synchronous Preprocessing**:
   - Audio preprocessing and DFT spectral extraction execute synchronously on CPU. While extremely fast (<3s for 2-sample batches), large multi-file batches will block the calling thread during enrollment.
