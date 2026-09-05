# V1.5 Known Limitations

## 1. Local CPU Execution Latency
Synthesizing speech on local CPU cores using `transformers` + `speechbrain` neural models incurs significant computational overhead. 
- **Piper/Edge-TTS Latency**: < 1.0s (highly optimized C++ / web streams).
- **SpeechT5 Neural Latency**: ~6.0s - 18.0s on standard CPU cores.
- *Mitigation*: In production deployments, configure a local CUDA-compatible GPU to drop synthesis latency to sub-second ranges.

## 2. Audio Sample Rate Discrepancy
- SpeechT5 generates waveforms fixed at **16,000 Hz** sample rates.
- This differs from Edge-TTS (24,000 Hz) and Piper (22,050 Hz). 
- *Mitigation*: The unified wrapper returns correct sample rates in metadata; downstream mixers should resample audio streams cleanly.

## 3. Dependency Footprint
The introduction of `speechbrain`, `transformers`, and `torch` packages expands the virtual environment footprint by ~2.5 GB on disk and introduces deep network weights downloads from HuggingFace Hub during cold-starts.
