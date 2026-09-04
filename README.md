# Aryntra Avni — V1.0: Reusable Voice Identity Foundation

Aryntra Avni is a long-term research and development system for **controllable synthetic identity**.

**V1.0 (Voice Identity Foundation)** establishes the system primitives for enrolling authorized voice recordings, extracting reusable voice representations, persisting profiles with consent and provenance, and synthesizing speech through stable identity boundaries.

---

## 1. Architectural Flow

`	ext
Authorized Voice Audio
          │
          ▼
   Voice Enrollment (src/enrollment/)
          │
          ▼
Voice Representation (src/representation/)
          │
          ▼
 Persistent Profile (src/profiles/)
          │
          ▼
   Voice Identity
          │
          ▼
   Voice Capability (src/capabilities/)
          │
    ┌─────┴─────┐
    ▼           ▼
 Edge-TTS     Piper (Offline)
    │           │
    └─────┬─────┘
          ▼
   Voice Response (Audio + Identity Metadata)
2. Quick Start & Setup
Prerequisites
Python 3.10+
Internet connection (for default neural cloud renderer, edge-tts)
Local ONNX model for offline synthesis (bundled in models/voices/)
Run Tests
Bash

python -m pytest tests/ -v
Run V1.0 Evaluation Benchmark
Bash

python experiments/voice/v1_eval.py
Run NAV Integration Demo
Bash

python scripts/enroll_and_speak_example.py
3. NAV Integration Guide (V1.0 Usage)
Python

from pathlib import Path
from src import create_default_voice_capability, VoiceRequest, AvniVoiceError
from src.enrollment import EnrollmentService, EnrollmentRequest, AudioSample
from src.representation import AcousticFeatureExtractor
from src.profiles import ProfileStore, VoiceIdentityProfile, ConsentRecord, ProvenanceRecord
from src.representation.base import VoiceRepresentation

# 1. Initialize capability (connects registry and persistent profile store)
voice_service = create_default_voice_capability()

# 2. Synthesize using either built-in identity or persistent profile
response = voice_service.synthesize(
    VoiceRequest(
        text="Greetings NAV. I am speaking through a persistent voice identity.",
        identity_id="avni_default",
        request_id="req_101",
    )
)

print(f"Generated {len(response.audio_bytes)} bytes in {response.metadata['generation_latency_sec']}s")
