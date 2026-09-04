# ADR 0010: Voice Identity Primitive, Persistent Profiles, and Capability Resolution

## Status
Accepted

## Context
In Avni V0 and V0.5, a \VoiceIdentity\ was a purely declarative configuration mapping an \identity_id\ to a static TTS voice (e.g. \en-US-AriaNeural\ on EdgeTTS or \en_US-lessac-medium\ on Piper). There was no mechanism to accept authorized human recordings, extract a reusable voice representation, or persist that identity across system restarts.

V1.0 introduces the **Voice Identity primitive** lifecycle:
1. Multi-recording enrollment with format and duration validation (\src/enrollment\).
2. Pluggable representation extraction (\src/representation\).
3. Persistent identity profiles with explicit consent and provenance (\src/profiles\).
4. On-demand identity resolution inside \VoiceCapability\.

## Decision
1. **Extend \VoiceIdentity\ without breaking existing consumers**:
   Add optional \epresentation_id\ and \profile_id\ fields to \VoiceIdentity\. All existing fields retain their default values. Existing declarative identities continue working identically.
2. **Pluggable Representation Extraction**:
   Introduce the \RepresentationExtractor\ ABC. In V1, implement \AcousticFeatureExtractor\ (pure Python, 5-dimensional acoustic statistics) to provide deterministic, zero-dependency identity extraction.
3. **Persistent Identity Storage**:
   Introduce \ProfileStore\ for atomic local filesystem persistence of \VoiceIdentityProfile\ (JSON metadata + base64 encoded representation).
4. **Transparent Capability Resolution**:
   Update \VoiceCapability\ to resolve identities first from the in-memory registry, then dynamically from \ProfileStore\. When synthesizing via a persistent profile identity, representation metadata is propagated into the response.

## Consequences
- NAV can synthesize speech using enrolled voice profile IDs with zero knowledge of underlying TTS engines, embedding formats, or storage layout.
- The voice identity boundary is fully decoupled from the renderer implementation.
- All existing V0.5 tests, adapters, and fallback policies remain 100% functional.
