# ADR 0008: Local TTS Renderer Selection (Piper ONNX)

## Context
V0.5 requires an offline speech synthesis capability that operates independently of network connectivity, while preserving the stable `TTSRenderer` contract.

## Evaluation & Evidence
We evaluated four local TTS engines against Python 3.13 on Windows x64:
1. **Piper TTS (piper-tts 1.8.0)**: Succeeded. Uses prebuilt ABI3 wheels and `onnxruntime` 1.29.0 cp313 wheels. High-quality neural synthesis on CPU.
2. **pyttsx3**: Succeeded via SAPI5, but robotic voice quality fails Avni's baseline naturalness standard. Retained as reference.
3. **Kokoro TTS**: Failed due to rigid dependency constraints (`numpy==1.26.4` compilation failure on Python 3.13).
4. **Coqui TTS**: Eliminated due to unmaintained repository and heavyweight PyTorch toolchain.

## Decision
1. Adopt **piper-tts** as the offline local renderer adapter (PiperTTSAdapter).
2. Encapsulate all Piper and ONNX runtime logic inside src/adapters/tts/piper_adapter.py.
3. The adapter will implement the existing TTSRenderer contract (enderer_id = "piper").
4. Local voice models (ONNX + JSON metadata) will be stored in a dedicated directory or loaded via configuration.
5. Update pyproject.toml and equirements.txt to include piper-tts.

## Consequences
- **Positive**: Avni gains high-quality, fully offline neural synthesis on standard consumer CPUs.
- **Positive**: Core contracts (VoiceRequest, VoiceResponse, TTSRenderer) remain completely untouched.
- **Trade-off**: Requires local model storage (~20-50MB per voice ONNX file).

## Status
Accepted
