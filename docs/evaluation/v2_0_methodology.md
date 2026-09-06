# V2.0 Real-Speech Evaluation Methodology

This document outlines the rigorous protocol used to evaluate the persistent Voice Identity and neural manifestation pipeline in **Aryntra Avni V2.0**.

---

## 1. Experimental Design

Our primary research question was:
> **Does Avni's persistent Voice Identity represent a meaningful and reproducible human voice identity when used with real human speech?**

To answer this without introducing bias, we enforced complete separation between enrollment data and evaluation data.

### Sample Layout

For each speaker under assessment:
Speaker ID (e.g., speaker_a)
├── Enrollment Samples (Used to extract voice representation)
│ ├── sample_1.wav (Phrase 1)
│ └── sample_2.wav (Phrase 2)
│
└── Held-Out Reference Samples (Used only as similarity baselines)
├── eval_1.wav (Phrase 3)
├── eval_2.wav (Phrase 4)
└── eval_3.wav (Phrase 5)


This prevents the system from "memorizing" specific phonetic content or sentence prosody and validates true speaker identity transfer.

---

## 2. Core Metrics

We track four distinct mathematical categories using the unit-normalized cosine similarity of extracted 512-dimensional neural speaker embeddings:

### A. Representation Consistency
- **Formula:** Similarity(Enrollment_Rep_A, Eval_Rep_A_i)
- **Goal:** Verify that multiple independent recordings of Speaker A yield consistent representations.

### B. Cross-Speaker Separation
- **Formula:** Similarity(Enrollment_Rep_A, Enrollment_Rep_B)
- **Goal:** Verify that different physical speakers remain mathematically distinct.

### C. Generated Identity Retention
- **Formula:** Similarity(Generated_A_Text_j, Eval_Rep_A_i)
- **Goal:** Measure if generated samples conditioned on Identity A retain Identity A's mathematical characteristics.

### D. Cross-Identity Generation (Identity Leakage / Collapsing)
- **Formula:** Similarity(Generated_A_Text_j, Eval_Rep_B_i)
- **Goal:** Confirm that Generated Speaker A does *not* drift toward Speaker B's reference characteristics.

---

## 3. Human Listening Evaluation Protocol

While cosine similarities of x-vectors are structurally useful, voice identity is fundamentally a perceptual phenomenon. We evaluated human perception using:

1. **Speaker Identification (ABX):** Listeners are presented with a generated sample and must associate it with the correct reference speaker (A or B).
2. **Pairwise Distinction:** Can listeners reliably tell if two generated samples are spoken by different voices?
3. **Similarity to Source (MOS):** Rating scale from 1 (entirely different) to 5 (identical voice).
4. **Naturalness (MOS):** Perceptual voice synthesis naturalness rating from 1 (unusable/fully synthetic) to 5 (completely natural/human).
