# 0013. Uniform Request-Time Expression Application in Voice Conversion

Date: 2025-03-01
Status: Accepted

## Context
During Avni V3.0 S1, request-time expression controls (pitch_scale, ate_scale, energy_scale) were introduced and hooked into the TTS synthesis manifestation pathway via SpeechT5Adapter._apply_expression. 

In V3.0 S2, during benchmark evaluation of real authorized human speech across a 16-condition matrix, empirical inspection revealed that SpeechT5VCAdapter received context but did not execute acoustic modulation on the generated waveform. Consequently, identity retention remained static and expression variations were unmanifested in VC mode.

## Decision
1. Implement _apply_expression within SpeechT5VCAdapter, identical in mathematical contract to SpeechT5Adapter.
2. Apply pitch shifting via 	orchaudio.functional.pitch_shift, time-stretching / rate modulation via scipy.signal.resample, and amplitude scaling with clamping to [-1.0, 1.0].
3. Preserve full backward compatibility: if context is None or expression is neutral (all scales == 1.0), raw model output is returned without modification.

## Consequences
- **Positive**: Voice Conversion and Text-to-Speech manifestation pipelines have uniform expression capabilities.
- **Positive**: Enables empirical quantification of the real human identity retention vs. expression modulation envelope.
- **Observed Trade-off**: Resampling-based rate modification introduces rate/pitch coupling that must be measured and documented in the S2 Operating Envelope.