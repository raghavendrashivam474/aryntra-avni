# V2.5 Known Limitations

1. **Neural Model Download Latency on Uncached Runtimes:**
   The `SpeechT5VCAdapter` uses `microsoft/speecht5_vc` from HuggingFace Hub. On initial cold-start without pre-cached weights, loading the neural converter requires network bandwidth and time. The system automatically falls back to `AcousticVCAdapter` if the neural model is unregistered or unavailable.

2. **Embedding Architecture Homogeneity:**
   SpeechT5 neural VC directly consumes Avni's 512-dimensional ECAPA-TDNN x-vectors. Alternative zero-shot models (such as Seed-VC or OpenVoice) require different embedding spaces (e.g., WavLM or Whisper encoder embeddings). Adapting to those models requires adapter-level embedding projection or reference-clip caching.

3. **Acoustic Fallback Timbre Range:**
   The `AcousticVCAdapter` shifts formants and fundamental frequency deterministically while perfectly preserving timing and prosody. However, it cannot alter phonetic articulation or vocal tract subtleties to the same degree as full neural diffusion or autoregressive models.

4. **Synchronous Execution:**
   Conversion currently executes synchronously per request. Streaming chunk-based conversion for real-time live teleoperation remains out of scope for V2.5.
