import os
import sys
import json
import wave
import hashlib
import numpy as np
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src import create_default_voice_capability
from src.contracts.voice import VoiceConversionRequest
from src.contracts.expression import ExpressionConfig
from src.capabilities.voice.capability import VoiceCapability
from src.capabilities.voice.registry import ConverterRegistry, IdentityRegistry
from src.profiles.profile_store import ProfileStore
from src.profiles.voice_profile import (
    VoiceIdentityProfile,
    ConsentRecord,
    ProvenanceRecord
)
from src.profiles.consent import ConsentStatus
from src.representation.neural_extractor import NeuralSpeakerExtractor
from src.adapters.voice_conversion.speecht5_vc_adapter import SpeechT5VCAdapter
from src.adapters.voice_conversion.acoustic_vc_adapter import AcousticVCAdapter

# ============================================================================
# Pure NumPy DSP Measurements (Zero External Dependencies)
# ============================================================================

def load_wav_samples(filepath: Path):
    """Loads a WAV file and returns float32 samples scaled to [-1.0, 1.0]."""
    with wave.open(str(filepath), 'rb') as w:
        params = w.getparams()
        n_channels, sampwidth, framerate, n_frames = params[:4]
        if sampwidth != 2:
            raise ValueError(f"Only 16-bit PCM WAV supported. Got width={sampwidth}")
        
        raw_data = w.readframes(n_frames)
        samples = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0
        
        if n_channels > 1:
            samples = samples.reshape(-1, n_channels).mean(axis=1)
            
        return samples, framerate

def write_wav_samples(filepath: Path, audio_data, sr: int = 16000):
    """Writes bytes or float [-1.0, 1.0] samples to 16-bit PCM WAV."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    if isinstance(audio_data, bytes):
        if audio_data.startswith(b'RIFF'):
            with open(filepath, 'wb') as f:
                f.write(audio_data)
        else:
            with wave.open(str(filepath), 'wb') as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(sr)
                w.writeframes(audio_data)
    elif isinstance(audio_data, np.ndarray):
        clipped = np.clip(audio_data * 32767.0, -32768.0, 32767.0).astype(np.int16)
        with wave.open(str(filepath), 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr)
            w.writeframes(clipped.tobytes())
    else:
        raise TypeError(f"Unsupported audio type: {type(audio_data)}")

def estimate_f0(samples: np.ndarray, sr: int, fmin=60, fmax=350) -> float:
    """Estimates median F0 (pitch) via autocorrelation."""
    if len(samples) == 0:
        return 0.0
    
    frame_size = int(sr * 0.040)  # 40ms window
    hop_size = int(sr * 0.020)    # 20ms hop
    min_period = int(sr / fmax)
    max_period = int(sr / fmin)
    
    f0_list = []
    
    for i in range(0, len(samples) - frame_size, hop_size):
        frame = samples[i:i+frame_size]
        frame = frame - np.mean(frame)
        std = np.std(frame)
        if std < 0.01:
            continue
            
        corr = np.correlate(frame, frame, mode='full')
        corr = corr[len(corr)//2:]
        
        if len(corr) <= max_period:
            continue
            
        search_region = corr[min_period:max_period]
        if len(search_region) == 0:
            continue
            
        peak_idx = np.argmax(search_region) + min_period
        
        if corr[peak_idx] > 0.25 * corr[0]:
            f0 = sr / peak_idx
            f0_list.append(f0)
            
    if len(f0_list) == 0:
        return 0.0
    return float(np.median(f0_list))

def estimate_rms(samples: np.ndarray) -> float:
    """Estimates Root Mean Square (RMS) energy."""
    if len(samples) == 0:
        return 0.0
    return float(np.sqrt(np.mean(samples ** 2)))

def detect_clipping(samples: np.ndarray, threshold=0.99) -> bool:
    """Detects if audio contains clipping samples."""
    if len(samples) == 0:
        return False
    return bool(np.any(np.abs(samples) >= threshold))

# ============================================================================
# Main S2 Evaluation Runner
# ============================================================================

def run_s2_benchmark():
    print("[+] Starting Avni V3.0 S2 Real Identity Evaluation Harness")
    
    project_root = Path(__file__).resolve().parents[3]
    auth_data_dir = project_root / "experiments/v3_0_identity_control/data/authorized"
    results_dir = project_root / "experiments/v3_0_identity_control/results/s2"
    results_dir.mkdir(parents=True, exist_ok=True)
    
    extractor = NeuralSpeakerExtractor()
    profile_store = ProfileStore(project_root / "data/profiles")
    
    spk_a_enroll_1 = auth_data_dir / "spk_a_enroll_1.wav"
    spk_a_enroll_2 = auth_data_dir / "spk_a_enroll_2.wav"
    
    print(f"[+] Deriving target voice profile for SPK_A_AUTH...")
    
    enrollment_bytes = [
        spk_a_enroll_1.read_bytes(),
        spk_a_enroll_2.read_bytes()
    ]
    
    rep_a = extractor.extract(enrollment_bytes)
    profile_id = "SPK_A_AUTH"
    
    ext_id = extractor.extractor_id() if callable(getattr(extractor, 'extractor_id', None)) else "neural_speaker_extractor"
    ext_ver = extractor.version() if callable(getattr(extractor, 'version', None)) else "1.0.0"
    
    consent_rec = ConsentRecord(
        source_id="SPK_A_AUTH",
        status=ConsentStatus.ACTIVE,
        scope="voice_identity_enrollment",
        terms_version="1.0"
    )
    
    provenance_rec = ProvenanceRecord(
        extractor_id=str(ext_id),
        extractor_version=str(ext_ver),
        sample_count=2,
        source_sample_hashes=[
            hashlib.sha256(enrollment_bytes[0]).hexdigest(),
            hashlib.sha256(enrollment_bytes[1]).hexdigest()
        ]
    )
    
    profile = VoiceIdentityProfile(
        identity_id=profile_id,
        representation=rep_a,
        consent=consent_rec,
        provenance=provenance_rec
    )
    profile_store.save(profile)
    print(f"    - Identity profile SPK_A_AUTH successfully saved into ProfileStore.")
    
    # Initialize converters
    converters = ConverterRegistry()
    speecht5_vc = SpeechT5VCAdapter()
    acoustic_vc = AcousticVCAdapter()
    converters.register(speecht5_vc)
    converters.register(acoustic_vc)
    
    voice_capability = VoiceCapability(
        profile_store=profile_store,
        converter_registry=converters
    )
    
    # Source Performance from Speaker B
    source_performance_path = auth_data_dir / "spk_b_perf_1.wav"
    source_bytes = source_performance_path.read_bytes()
    source_samples, source_sr = load_wav_samples(source_performance_path)
    source_f0 = estimate_f0(source_samples, source_sr)
    source_rms = estimate_rms(source_samples)
    source_dur = len(source_samples) / source_sr
    
    print(f"\n[+] Baseline Source Performance (Speaker B):")
    print(f"    - File: {source_performance_path.name}")
    print(f"    - Pitch (F0): {source_f0:.2f} Hz")
    print(f"    - Energy (RMS): {source_rms:.4f}")
    print(f"    - Duration: {source_dur:.2f} s\n")
    
    conditions = [
        # Neutral Baseline
        {"name": "neutral", "pitch": 1.0, "rate": 1.0, "energy": 1.0},
        
        # Pitch Modulation Envelope
        {"name": "pitch_low_extreme", "pitch": 0.5, "rate": 1.0, "energy": 1.0},
        {"name": "pitch_low", "pitch": 0.75, "rate": 1.0, "energy": 1.0},
        {"name": "pitch_high", "pitch": 1.35, "rate": 1.0, "energy": 1.0},
        {"name": "pitch_high_extreme", "pitch": 1.8, "rate": 1.0, "energy": 1.0},
        
        # Rate Modulation Envelope
        {"name": "rate_slow_extreme", "pitch": 1.0, "rate": 0.5, "energy": 1.0},
        {"name": "rate_slow", "pitch": 1.0, "rate": 0.75, "energy": 1.0},
        {"name": "rate_fast", "pitch": 1.0, "rate": 1.35, "energy": 1.0},
        {"name": "rate_fast_extreme", "pitch": 1.0, "rate": 1.8, "energy": 1.0},
        
        # Energy Modulation Envelope
        {"name": "energy_low_extreme", "pitch": 1.0, "rate": 1.0, "energy": 0.5},
        {"name": "energy_low", "pitch": 1.0, "rate": 1.0, "energy": 0.75},
        {"name": "energy_high", "pitch": 1.0, "rate": 1.0, "energy": 1.35},
        {"name": "energy_high_extreme", "pitch": 1.0, "rate": 1.0, "energy": 1.8},
        
        # Combined Expression Envelope
        {"name": "combined_slow_low", "pitch": 0.75, "rate": 0.75, "energy": 0.8},
        {"name": "combined_fast_high", "pitch": 1.35, "rate": 1.35, "energy": 1.2},
        {"name": "combined_extreme_mix", "pitch": 1.5, "rate": 0.6, "energy": 1.4}
    ]
    
    results = []
    
    for cond in conditions:
        cond_name = cond["name"]
        p_scale = cond["pitch"]
        r_scale = cond["rate"]
        e_scale = cond["energy"]
        
        print(f"Executing condition: {cond_name:<25} [P: {p_scale:.2f}, R: {r_scale:.2f}, E: {e_scale:.2f}]")
        
        context_payload = {
            "expression": {
                "pitch_scale": p_scale,
                "rate_scale": r_scale,
                "energy_scale": e_scale
            }
        }
        
        req = VoiceConversionRequest(
            source_audio_bytes=source_bytes,
            target_identity_id=profile_id,
            context=context_payload
        )
        
        try:
            response = voice_capability.convert(req)
            
            output_path = results_dir / f"output_s2_{cond_name}.wav"
            
            sr = getattr(response, 'sample_rate', 16000)
            write_wav_samples(output_path, response.audio_bytes, sr)
            
            gen_samples, gen_sr = load_wav_samples(output_path)
            gen_f0 = estimate_f0(gen_samples, gen_sr)
            gen_rms = estimate_rms(gen_samples)
            gen_dur = len(gen_samples) / gen_sr
            gen_clipping = detect_clipping(gen_samples)
            
            gen_bytes = output_path.read_bytes()
            gen_rep = extractor.extract([gen_bytes])
            
            similarity = float(extractor.similarity(rep_a, gen_rep))
            
            f0_shift_ratio = gen_f0 / source_f0 if source_f0 > 0 and gen_f0 > 0 else 0.0
            dur_ratio = gen_dur / source_dur if source_dur > 0 else 0.0
            energy_ratio = gen_rms / source_rms if source_rms > 0 else 0.0
            
            print(f"    -> Similarity: {similarity:.4f} | F0 Shift: {f0_shift_ratio:.2f}x | Dur Shift: {dur_ratio:.2f}x | Clipping: {gen_clipping}")
            
            results.append({
                "condition": cond_name,
                "parameters": cond,
                "metrics": {
                    "identity_similarity": round(similarity, 4),
                    "measured_f0_hz": round(gen_f0, 2),
                    "measured_rms": round(gen_rms, 4),
                    "measured_duration_sec": round(gen_dur, 2),
                    "f0_shift_ratio": round(f0_shift_ratio, 3),
                    "duration_ratio": round(dur_ratio, 3),
                    "energy_ratio": round(energy_ratio, 3),
                    "clipping_detected": gen_clipping,
                    "audio_file": str(output_path.as_posix())
                },
                "status": "SUCCESS"
            })
            
        except Exception as e:
            print(f"    [-] Condition FAILED: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({
                "condition": cond_name,
                "parameters": cond,
                "status": "FAILED",
                "error": str(e)
            })
            
    output_report_json = results_dir / "s2_matrix_results.json"
    with open(output_report_json, "w", encoding="utf-8") as f:
        json.dump({
            "project": "Aryntra Avni V3.0 S2 Real Identity Evaluation",
            "source_speaker": "SPK_B_AUTH",
            "target_identity": "SPK_A_AUTH",
            "source_baseline": {
                "f0_hz": round(source_f0, 2),
                "rms": round(source_rms, 4),
                "duration_sec": round(source_dur, 2)
            },
            "runs": results
        }, f, indent=2)
        
    print(f"\n[+] Comprehensive S2 Benchmark evaluation complete.")
    print(f"    Data written to: {output_report_json}")

if __name__ == "__main__":
    run_s2_benchmark()