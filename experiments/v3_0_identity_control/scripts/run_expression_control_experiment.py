"""V3.0 S1 Experiment: Controlled Expression Manifestation & Identity Retention.

Executes 8 controlled conditions to prove:
1. Manifestation boundary responds reliably to ExpressionConfig (Pitch, Rate, Energy).
2. Persistent Voice Identity remains retained (>90% similarity).
3. Persistent identity data remains untouched (read-only).
"""

import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import json
import time
import math
import struct
import tempfile
import numpy as np
import soundfile as sf

from src import create_default_voice_capability, VoiceRequest
from src.contracts.expression import ExpressionConfig
from src.representation.neural_extractor import NeuralSpeakerExtractor
from src.contracts.voice import VoiceIdentity

RESULTS_DIR = os.path.join(REPO_ROOT, "experiments/v3_0_identity_control/results")
os.makedirs(RESULTS_DIR, exist_ok=True)
RESULTS_PATH = os.path.join(RESULTS_DIR, "s1_results.json")

def generate_synthetic_identity_embedding(seed: int = 42) -> bytes:
    """Generate deterministic 512-dim embedding for testing."""
    rng = np.random.RandomState(seed)
    vec = rng.randn(512).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return struct.pack(f"<512f", *vec)

def compute_audio_metrics(wav_bytes: bytes, sample_rate: int = 16000):
    """Compute F0, duration, and RMS energy using soundfile & autocorrelation."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        tf.write(wav_bytes)
        tpath = tf.name

    try:
        y, sr = sf.read(tpath)
        if y.ndim > 1:
            y = y.mean(axis=1)
        y = y.astype(np.float32)
        duration = float(len(y) / sr)

        # RMS Energy
        rms = float(np.sqrt(np.mean(y**2)))

        # F0 estimation via autocorrelation over frame blocks
        frame_len = int(sr * 0.04)  # 40ms frame
        hop_len = int(sr * 0.01)    # 10ms hop
        min_lag = int(sr / 400)     # max 400Hz
        max_lag = int(sr / 60)      # min 60Hz

        f0_estimates = []
        for start in range(0, len(y) - frame_len, hop_len):
            frame = y[start:start + frame_len]
            if np.sum(frame**2) < 1e-4:
                continue
            corr = np.correlate(frame, frame, mode='full')
            corr = corr[len(frame)-1:]
            if len(corr) > max_lag:
                peak_lag = min_lag + np.argmax(corr[min_lag:max_lag])
                if peak_lag > 0 and corr[peak_lag] > 0.3 * corr[0]:
                    f0 = sr / float(peak_lag)
                    f0_estimates.append(f0)

        mean_f0 = float(np.mean(f0_estimates)) if len(f0_estimates) > 0 else 0.0

        return {
            "duration_sec": round(duration, 3),
            "rms_energy": round(rms, 5),
            "mean_f0_hz": round(mean_f0, 2),
            "sample_count": len(y)
        }, y
    finally:
        if os.path.exists(tpath):
            os.remove(tpath)

def main():
    print("=" * 75)
    print("V3.0 S1 Controlled Expression Manifestation Benchmark")
    print("=" * 75)
    print("Initializing Avni Voice Capability and Neural Speaker Extractor...")
    capability = create_default_voice_capability()
    extractor = NeuralSpeakerExtractor(device="cpu")

    # 1. Register a persistent test identity
    target_identity_id = "s1-target-speaker"
    target_emb_bytes = generate_synthetic_identity_embedding(seed=101)

    target_identity = VoiceIdentity(
        identity_id=target_identity_id,
        renderer_id="speecht5",
        voice_configuration={
            "representation_data": target_emb_bytes,
            "sample_rate": 16000
        }
    )
    capability.identities.register(target_identity)

    # 2. Define standard test text and conditions
    test_text = "Speech manifestation must decouple identity from expression state."
    
    conditions = [
        {"name": "baseline_neutral", "config": ExpressionConfig.neutral()},
        {"name": "pitch_high", "config": ExpressionConfig(pitch_scale=1.20)},
        {"name": "pitch_low", "config": ExpressionConfig(pitch_scale=0.80)},
        {"name": "rate_fast", "config": ExpressionConfig(rate_scale=1.25)},
        {"name": "rate_slow", "config": ExpressionConfig(rate_scale=0.80)},
        {"name": "energy_high", "config": ExpressionConfig(energy_scale=1.30)},
        {"name": "energy_low", "config": ExpressionConfig(energy_scale=0.70)},
        {"name": "combined_expressive", "config": ExpressionConfig(pitch_scale=1.15, rate_scale=1.10, energy_scale=1.20)},
    ]

    print(f"\nEvaluating 8 experimental conditions for '{target_identity_id}'...")
    results = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "identity_id": target_identity_id,
        "text": test_text,
        "conditions": {}
    }

    baseline_rep = None

    for cond in conditions:
        c_name = cond["name"]
        expr = cond["config"]
        print(f"\n--> Synthesizing condition: [{c_name}] (pitch={expr.pitch_scale}, rate={expr.rate_scale}, energy={expr.energy_scale})")
        
        req = VoiceRequest(
            text=test_text,
            identity_id=target_identity_id,
            expression=expr
        )
        
        t0 = time.perf_counter()
        resp = capability.synthesize(req)
        latency = time.perf_counter() - t0

        metrics, audio_samples = compute_audio_metrics(resp.audio_bytes)
        metrics["latency_sec"] = round(latency, 3)

        # Extract neural representation for identity retention evaluation
        sample_rep = extractor.extract([resp.audio_bytes])

        if c_name == "baseline_neutral":
            baseline_rep = sample_rep
            similarity_to_baseline = 1.0
        else:
            similarity_to_baseline = float(extractor.similarity(baseline_rep, sample_rep))

        metrics["identity_retention_pct"] = round(similarity_to_baseline * 100.0, 2)
        results["conditions"][c_name] = {
            "expression_config": {
                "pitch_scale": expr.pitch_scale,
                "rate_scale": expr.rate_scale,
                "energy_scale": expr.energy_scale
            },
            "metrics": metrics
        }

        print(f"    Duration: {metrics['duration_sec']}s | F0: {metrics['mean_f0_hz']}Hz | RMS: {metrics['rms_energy']} | Identity Retention: {metrics['identity_retention_pct']}%")

    # 3. Save results JSON
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 75)
    print(f"[SUCCESS] Results saved to: {RESULTS_PATH}")
    print("=" * 75)

if __name__ == "__main__":
    main()
