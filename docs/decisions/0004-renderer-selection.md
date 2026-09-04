# ADR 0004: Initial TTS Renderer Selection (Edge-TTS)

## Context
V0 requires at least one working TTS engine adapter behind the `TTSRenderer` interface so NAV can receive real synthesized audio.

## Options Considered
1. **Pyttsx3 (SAPI5):** Fully offline, but robotic voice quality fails naturalness standards.
2. **Coqui TTS / Bark:** High quality, but requires gigabytes of PyTorch dependencies and GPU setup.
3. **Edge-TTS:** High naturalness (neural voice), zero API keys, lightweight python package, fast synthesis.

## Decision
Adopt **`edge-tts`** as the default V0 TTS adapter (`EdgeTTSAdapter`).
The adapter will be completely encapsulated in `src/adapters/tts/edge_tts_adapter.py`.

## Consequences
- Clean, natural-sounding audio output for NAV testing.
- Avni core contracts remain completely unaware of `edge-tts`.
- Offline local rendering can be added later as an alternative adapter (e.g., Piper) without modifying `VoiceCapability`.

## Status
Accepted