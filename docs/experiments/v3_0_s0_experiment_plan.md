# V3.0 S0 — Experiment Plan & Methodology

> **Milestone:** Aryntra Avni V3.0 — Identity Control & Disentanglement
> **Status:** Research Experiment S0

---

## 1. Objective

Determine whether Avni can vary expression (tempo, prosody, rhythm, pitch dynamics) while preserving persistent voice identity ($I_{\text{target}}$) without identity drift.

---

## 2. Hypothesis & Evaluation Matrix

### 2.1 The Disentanglement Hypothesis
$$\text{Expression Difference} \uparrow \quad \text{and} \quad \text{Identity Retention } (I_{\text{retention}}) \approx \text{Constant High}$$

### 2.2 Measurement Formulations
1. **Target Identity Retention ($I_{\text{retention}}$):**
   $$I_{\text{retention}} = \text{CosineSimilarity}(\vec{e}_{\text{target}}, \vec{e}_{\text{converted}})$$
   *Extracted using the deep neural x-vector encoder (`speechbrain/spkrec-xvect-voxceleb`).*

2. **Acoustic / Prosodic Metrics:**
   - **Pitch Mean & Std Dev ($F_0$):** Measures fundamental frequency modulation across conditions.
   - **Temporal Duration ($T_{\text{sec}}$):** Measures temporal alignment and speaking pace adherence to source performance.
   - **RMS Energy:** Measures intensity dynamics.

---

## 3. Experimental Setup

- **Target Voice Identity:** Speaker A (`speaker_a.json`) with an enrolled 512-dim unit-normalized neural speaker embedding.
- **Source Performances:** 3 distinct evaluation utterances from Speaker B (`eval_1.wav`, `eval_2.wav`, `eval_3.wav`) providing varying duration, prosody, and higher pitch (~216Hz - 229Hz).
- **Transformation Engine:** `SpeechT5VCAdapter` (Neural Speech-to-Speech Conversion).

---
