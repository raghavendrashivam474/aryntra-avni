# Aryntra Avni — V0: Voice Foundation

Aryntra Avni is a long-term research and development system for **controllable synthetic identity**. 

The first domain of exploration is voice. Ultimately, Avni will evolve to explore composite synthetic voices, dynamic context-driven voice composition, expressive identity, adaptive behavior, and multi-modal synthetic identity (voice, language, behavior, and visuals).

**V0 (Voice Foundation)** establishes the clean architectural abstractions, boundaries, and validation engines required to support future synthetic identity research without prematurely coupling consuming systems (like NAV) to raw, volatile TTS engines.

---

## 1. Architectural Boundary

A core principle of Aryntra Avni is: **Stable abstractions, replaceable implementations.** 

Consumers (such as NAV) depend strictly on Avni's high-level voice capability contract, completely isolated from specific text-to-speech (TTS) engines, third-party software development kits (SDKs), or hosting providers.

```text
                         NAV
                          │
                          │ VoiceRequest (Text + Identity ID)
                          ▼
                    ┌───────────┐
                    │   Avni    │
                    │ Voice API │
                    └─────┬─────┘
                          │
                    Voice Identity (Resolved from configuration)
                          │
                    Renderer Contract (TTSRenderer Interface)
                          │
                    TTS Adapter (e.g., EdgeTTSAdapter)
                          │
                          ▼
                    VoiceResponse (Raw Audio Bytes + Metadata)
```

### Separation of Concerns: Identity vs. Renderer
A voice identity is a stable concept (e.g., *"the stable persona of Avni"*); a renderer is an interchangeable execution detail.
* **Voice Identity:** Who is speaking (governed by static profile files containing metadata and voice configurations).
* **Renderer:** How they are speaking (the underlying technical TTS engine mapped via an adapter class).

---

## 2. Directory Structure

```text
aryntra-avni/
│
├── artifacts/                  # Generated demo audio and evaluation outputs (.mp3, .wav)
├── configs/
│   └── identities/            # Declarative JSON voice identity profiles
│
├── docs/                      # Architectural Decisions (ADRs), vision, and roadmaps
│   ├── architecture/
│   ├── decisions/             # Standardized ADRs (0001 - 0006)
│   ├── evaluation/            # Automated benchmark evaluation outputs
│   └── vision/
│
├── experiments/
│   └── voice/                 # Latency, throughput, and performance benchmarks
│
├── scripts/                   # Integration simulators and helper utilities
│
├── src/
│   ├── contracts/             # Immutable data structures and interface ABCs (Zero Dependencies)
│   ├── capabilities/          # High-level orchestrators (e.g., VoiceCapability, IdentityLoader)
│   └── adapters/              # Concrete integrations bridging contracts to specific engines
│
└── tests/                     # Unit, contract, and end-to-end integration test suites
```

---

## 3. Quick Start & Setup

### Prerequisites
* **Python 3.10+**
* Internet connection (for the default neural cloud renderer, `edge-tts`)

### 1. Install Dependencies
Avni’s core runtime has zero third-party dependencies. To run the default neural renderer adapter, install `edge-tts`:
```bash
pip install edge-tts
```

### 2. Run the Test Suite
Verify that all contract validations, loaders, registries, adapters, and integration patterns are functioning correctly:
```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

### 3. Run the NAV Integration Demo
Simulate how NAV interacts with Avni. This script generates a synthesized audio file inside `artifacts/nav_sample_output.mp3`:
```bash
python scripts/nav_speak_example.py
```

### 4. Run the Quality & Latency Benchmark
Run a automated multi-iteration latency and reliability benchmark. Results will be saved inside `docs/evaluation/v0_results.md`:
```bash
python experiments/voice/v0_eval.py
```

---

## 4. NAV Integration Guide (API Usage)

NAV interacts with Avni purely in-process using simple, high-level constructs.

```python
from pathlib import Path
from src import create_default_voice_capability, VoiceRequest, AvniVoiceError

# 1. Initialize the capability (loads identities & registers default renderers)
voice_service = create_default_voice_capability()

try:
    # 2. Issue a structured voice request using an Identity ID
    response = voice_service.synthesize(
        VoiceRequest(
            text="Greetings NAV. I am speaking through a stable identity boundary.",
            identity_id="avni_default",
            request_id="unique_req_101"
        )
    )
    
    # 3. Access clean outputs
    audio_format = response.audio_format      # "mp3"
    audio_data = response.audio_bytes         # Raw binary bytes
    latency = response.metadata["generation_latency_sec"]
    
    print(f"Synthesized successfully in {latency}s!")

except AvniVoiceError as e:
    # 4. Handle wrapped, predictable domain errors
    print(f"Voice generation failed: Code={e.code} | Message={e.message}")
```

---

## 5. Built-In Voice Identities (V0)

The system currently exposes two voice identities configured in `configs/identities/`:

| Identity ID | Target Renderer ID | Target Neural Voice | Tone / Persona |
| :--- | :--- | :--- | :--- |
| `avni_default` | `edge_tts` | `en-US-AriaNeural` | Clean, crisp, professional assistant (Female) |
| `avni_guy` | `edge_tts` | `en-US-GuyNeural` | Steady, calm, clear helper persona (Male) |

To add or modify identities, simply place or update the corresponding `.json` profile in `configs/identities/`.

---

## 6. V0 Evaluation Benchmarks

A 9-iteration stability and latency test demonstrates the following operational metrics:

* **Fidelity & Naturalness:** High-quality neural vocoding.
* **Success Rate:** **100.0%** (zero failures or dropped frames).
* **Warm-Call Median Latency:** **~0.99 seconds** (sub-second performance).
* **Cold-Start Startup Latency:** ~2.42 seconds (initial TCP/network handshake).

---

## 7. Operational Guidelines (For Developers)

1. **Guard the Public Boundary:** Raw exceptions from underlying TTS packages must *never* leak through the public interface. Always wrap engine exceptions inside `AvniVoiceError` in the adapter layer.
2. **Abstract Over Engines:** No file in `src/contracts/` or `src/capabilities/` should ever import `edge_tts` or any other vendor library. Concrete vendor-specific logic belongs exclusively in `src/adapters/`.
3. **No Premature Complexity:** V0 is strictly an in-process, static voice configuration baseline. Do not introduce microservices, network brokers (gRPC/HTTP API servers), databases, or voice cloning features yet. Keep the boundaries ready, but keep the implementation minimal.