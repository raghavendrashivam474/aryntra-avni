"""
Aryntra Avni V3.0 S0 — Identity Control & Disentanglement Experiment.
Investigates whether Avni can vary voice expression while preserving persistent identity.
"""

import sys
import os
import json
import base64
import struct
import numpy as np
import wave
import io
import logging

# Set up logging to console
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("v3_s0_experiment")

# Ensure repository root is in sys.path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, repo_root)

try:
    from src.adapters.voice_conversion.speecht5_vc_adapter import SpeechT5VCAdapter
    from src.representation.neural_extractor import NeuralSpeakerExtractor
    from src.representation.base import VoiceRepresentation
    logger.info("Successfully imported Avni core modules.")
except ImportError as e:
    logger.error("Could not import Avni core modules: %s", e)
    sys.exit(1)


def load_profile_embedding(profile_path: str) -> VoiceRepresentation:
    """Load representation data directly from a persisted voice profile JSON."""
    with open(profile_path, "r", encoding="utf-8") as f:
        profile_data = json.load(f)
    
    rep_dict = profile_data["representation"]
    data_bytes = base64.b64decode(rep_dict["data_b64"])
    
    return VoiceRepresentation(
        representation_id=rep_dict["representation_id"],
        version=rep_dict["version"],
        data=data_bytes,
        metadata=rep_dict.get("metadata", {})
    )


def extract_f0_features(audio_bytes: bytes) -> dict:
    """
    Compute basic pitch and temporal characteristics from raw WAV audio bytes
    to demonstrate acoustic changes across expression conditions.
    """
    try:
        with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
            channels = wf.getnchannels()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw_audio = wf.readframes(n_frames)
        
        waveform = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32) / 32767.0
        if channels > 1:
            waveform = waveform.reshape(-1, channels).mean(axis=1)
        
        duration = len(waveform) / sample_rate
        
        # Simple Autocorrelation-based pitch detector for rough F0 estimation
        frame_size = int(0.030 * sample_rate)  # 30ms frames
        hop_size = int(0.015 * sample_rate)   # 15ms hop
        f0s = []
        
        for i in range(0, len(waveform) - frame_size, hop_size):
            frame = waveform[i:i + frame_size]
            # Standard autocorrelation
            corr = np.correlate(frame, frame, mode="full")
            corr = corr[len(corr)//2:]
            
            # Find peaks corresponding to typical voice pitch (50Hz - 400Hz)
            min_lag = int(sample_rate / 400)
            max_lag = int(sample_rate / 50)
            
            if min_lag < len(corr):
                peak = np.argmax(corr[min_lag:min_lag + (max_lag - min_lag)]) + min_lag
                if corr[peak] > 0.15 * corr[0]:  # Voicing threshold
                    f0s.append(sample_rate / peak)
        
        if f0s:
            pitch_mean = float(np.mean(f0s))
            pitch_std = float(np.std(f0s))
            pitch_max = float(np.max(f0s))
        else:
            pitch_mean, pitch_std, pitch_max = 0.0, 0.0, 0.0
            
        # Energy metrics
        rms_energy = float(np.sqrt(np.mean(waveform ** 2)))
        
        return {
            "duration_sec": round(duration, 3),
            "pitch_mean_hz": round(pitch_mean, 2),
            "pitch_std_hz": round(pitch_std, 2),
            "pitch_max_hz": round(pitch_max, 2),
            "rms_energy": round(rms_energy, 4)
        }
    except Exception as e:
        logger.warning("Failed to extract acoustic metrics: %s", e)
        return {"error": str(e)}


def run_experiment():
    profile_path = os.path.join(repo_root, "data", "evaluation", "output", "profiles", "speaker_a.json")
    if not os.path.exists(profile_path):
        logger.error("Target speaker profile path does not exist: %s", profile_path)
        sys.exit(1)
        
    logger.info("Loading Target Speaker A Profile...")
    target_rep = load_profile_embedding(profile_path)
    
    # We will run 3 source audio files representing diverse speaking tempos/styles
    source_wav_paths = [
        os.path.join(repo_root, "data", "evaluation", "speaker_b", "evaluation", "eval_1.wav"),
        os.path.join(repo_root, "data", "evaluation", "speaker_b", "evaluation", "eval_2.wav"),
        os.path.join(repo_root, "data", "evaluation", "speaker_b", "evaluation", "eval_3.wav"),
    ]
    
    for path in source_wav_paths:
        if not os.path.exists(path):
            logger.error("Required source audio not found: %s", path)
            sys.exit(1)

    # Initialize neural modules
    logger.info("Initializing neural components (SpeechT5, SpeechBrain)...")
    converter = SpeechT5VCAdapter(device="cpu")
    extractor = NeuralSpeakerExtractor(device="cpu")
    
    # Run lazy-loading now to log setup progress
    converter._load_components()
    
    results = []
    
    for idx, src_path in enumerate(source_wav_paths):
        condition_name = f"condition_{idx + 1}_source_b_eval_{idx + 1}"
        logger.info("--- Processing Condition: %s ---", condition_name)
        
        with open(src_path, "rb") as f:
            source_bytes = f.read()
            
        source_metrics = extract_f0_features(source_bytes)
        logger.info("Source Audio Metrics: %s", source_metrics)
        
        # Perform Voice Conversion using the target representation
        voice_config = {
            "representation_data": target_rep.data
        }
        
        logger.info("Performing voice conversion to Target Identity...")
        render_result = converter.convert(source_bytes, voice_config)
        output_bytes = render_result.audio_bytes
        
        # Save output wav to the results folder
        out_wav_name = f"output_converted_{condition_name}.wav"
        out_wav_path = os.path.join(repo_root, "experiments", "v3_0_identity_control", "results", out_wav_name)
        with open(out_wav_path, "wb") as f_out:
            f_out.write(output_bytes)
            
        logger.info("Output saved to %s", out_wav_path)
        
        # Extract representation from the converted output to verify identity retention
        logger.info("Extracting identity representation from converted output...")
        output_rep = extractor.extract([output_bytes])
        
        # Calculate Cosine Similarity to Target Identity
        similarity_score = extractor.similarity(target_rep, output_rep)
        logger.info("Target Identity Retention Score: %.4f", similarity_score)
        
        # Extract output acoustic metrics
        output_metrics = extract_f0_features(output_bytes)
        logger.info("Converted Audio Metrics: %s", output_metrics)
        
        results.append({
            "condition": condition_name,
            "source_file": os.path.basename(src_path),
            "output_file": out_wav_name,
            "target_identity_similarity": round(similarity_score, 4),
            "source_metrics": source_metrics,
            "converted_metrics": output_metrics
        })
        
    # Write full analysis report
    report = {
        "experiment": "v3_0_s0_disentanglement_spike",
        "target_profile": "speaker_a",
        "status": "success",
        "results": results
    }
    
    report_json_path = os.path.join(repo_root, "experiments", "v3_0_identity_control", "results", "s0_results.json")
    with open(report_json_path, "w", encoding="utf-8") as f_rep:
        json.dump(report, f_rep, indent=2)
        
    logger.info("==========================================")
    logger.info("EXPERIMENT COMPLETE. Summary of results:")
    for res in results:
        logger.info(
            "Condition: %s | Similarity: %.2f%% | Source Pitch: %.1fHz -> Converted: %.1fHz",
            res["condition"],
            res["target_identity_similarity"] * 100,
            res["source_metrics"].get("pitch_mean_hz", 0),
            res["converted_metrics"].get("pitch_mean_hz", 0)
        )
    logger.info("Full experiment report saved to %s", report_json_path)


if __name__ == "__main__":
    run_experiment()
