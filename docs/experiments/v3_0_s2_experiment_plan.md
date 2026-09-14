# Avni V3.0 S2 — Experiment Plan

## 1. Research Objectives
* To map the **Identity × Expression Operating Envelope** of Avni under varying scales of pitch, rate, and energy using real authorized human speech.
* To mathematically observe degradation levels across:
  * Individual variables (Pitch, Rate, Energy)
  * Combined parameters (e.g., Fast + High Pitch)
* To explicitly evaluate and log the degree of Rate ↔ Pitch coupling.

## 2. Experimental Roles
* **Speaker A**: Enrolls voice data to generate Synthetic Identity A (used as target identity).
* **Speaker B**: Executes the source performance (the source speech).
* **Avni Manifestation**: Takes Speaker B's speech and converts it to sound like Synthetic Identity A, modulated by Expression $.

## 3. Evaluation Dimensions
For each run, we measure:
* **Identity Retention**: Cosine similarity of neural embeddings between baseline and generated output.
* **Expression Effectiveness**:
  * Delta Pitch ($\Delta$ F0)
  * Delta Duration/Rate ($\Delta$ Secs)
  * Delta Energy ($\Delta$ RMS)
* **Audio Integrity**: File validation, clipping checks, and sample integrity.
