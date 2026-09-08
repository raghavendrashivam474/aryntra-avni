# V2.5 Initial Inspection Report

**Date:** 2026-09-09
**Baseline:** v2.0.0 — 82/82 tests passing
**Branch:** feat/v2.5-speech-to-voice

## 1. Current Architecture Summary

### Identity Pipeline (V1.0 → V2.0)
Authorized Audio → Enrollment → NeuralSpeakerExtractor (512-dim x-vector)
→ VoiceRepresentation → VoiceIdentityProfile → ProfileStore (JSON)
→ IdentityLoader → VoiceIdentity (with representation_data in voice_config)
→ VoiceCapability.synthesize() → TTSRenderer → Audio

text


### Key Contracts Inspected

| Contract | File | Reusable for VC? |
|---|---|---|
| VoiceRequest | contracts/voice.py | NO — text-oriented |
| VoiceResponse | contracts/voice.py | YES — audio output |
| VoiceIdentity | contracts/voice.py | YES — carries representation_data |
| TTSRenderer | contracts/renderer.py | NO — render(text,...) is TTS-specific |
| RenderResult | contracts/renderer.py | YES — generic audio output |
| VoiceRepresentation | representation/base.py | YES — persistent identity |
| VoiceIdentityProfile | profiles/voice_profile.py | YES — do not modify |
| ProfileStore | profiles/profile_store.py | YES — do not modify |
| VoiceCapability | capabilities/voice/capability.py | EXTEND — add convert() |
| IdentityLoader | capabilities/voice/identity_loader.py | YES — already injects rep data |
| EnrollmentService | enrollment/enrollment_service.py | YES — do not modify |

## 2. Critical Findings

### Finding 1: TTSRenderer Cannot Represent VC
`TTSRenderer.render(text, voice_config, context)` takes text input.
Voice conversion takes source audio input. Forcing VC into this contract
would create semantic confusion and violate the kernel/principle boundary.

**Decision:** Create sibling `VoiceConverter` abstraction (Option B from brief).

### Finding 2: Representation Data Already Flows
`IdentityLoader.load_from_profile()` already injects
`representation_data` (raw 512-dim float32 bytes) into
`voice_configuration`. The VC adapter can read this directly.

### Finding 3: Representation Compatibility Gap (Outcome B)
Current representation: 512-dim ECAPA-TDNN x-vector (speechbrain).
Seed-VC and similar models use WavLM-based embeddings or raw reference audio.
The VC adapter must handle this translation at the plugin boundary.

**Strategy:** VC adapter receives target identity's reference audio
(stored alongside profile, not inside it) and handles model-specific
conditioning internally. The persistent x-vector remains canonical
for identity verification and TTS.

### Finding 4: VoiceCapability Needs Parallel Path
`VoiceCapability.synthesize()` handles TTS. A sibling `convert()`
method will handle VC using the same identity resolution pipeline.

## 3. Files Expected to Change

| File | Change Type |
|---|---|
| src/contracts/renderer.py | ADD VoiceConverter ABC |
| src/contracts/voice.py | ADD VoiceConversionRequest |
| src/capabilities/voice/capability.py | ADD convert() method |
| src/capabilities/voice/registry.py | ADD ConverterRegistry |
| src/adapters/voice_conversion/ | NEW directory + adapter |

## 4. Files Intentionally Untouched

- src/contracts/voice.py (existing classes — only additions)
- src/representation/base.py
- src/representation/neural_extractor.py
- src/profiles/voice_profile.py
- src/profiles/profile_store.py
- src/profiles/consent.py
- src/enrollment/*
- src/adapters/tts/*
- src/capabilities/voice/identity_loader.py

## 5. Technical Hypothesis

The same persistent VoiceIdentityProfile can manifest through both
TTS (SpeechT5) and VC (Seed-VC) pathways without modifying the
identity representation, profile schema, or enrollment pipeline.
The VC adapter will consume reference audio stored alongside the
profile and handle model-specific conditioning at the plugin boundary.
