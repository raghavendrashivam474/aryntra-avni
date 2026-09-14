import os
import json
import hashlib
import wave
from pathlib import Path

def get_wav_meta(filepath: Path):
    with wave.open(str(filepath), 'rb') as w:
        nchannels = w.getnchannels()
        framerate = w.getframerate()
        nframes = w.getnframes()
        duration = round(nframes / float(framerate), 3)
    return nchannels, framerate, duration

def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def build_manifest():
    auth_dir = Path("experiments/v3_0_identity_control/data/authorized")
    meta_dir = Path("experiments/v3_0_identity_control/data/metadata")
    meta_dir.mkdir(parents=True, exist_ok=True)
    
    spk_a_files = ["spk_a_enroll_1.wav", "spk_a_enroll_2.wav"]
    spk_b_files = ["spk_b_perf_1.wav", "spk_b_perf_2.wav", "spk_b_perf_3.wav"]
    
    def process_files(file_list):
        entries = []
        for fname in file_list:
            fpath = auth_dir / fname
            if not fpath.exists():
                raise FileNotFoundError(f"Missing audio: {fpath}")
            channels, rate, dur = get_wav_meta(fpath)
            sha = calculate_sha256(fpath)
            entries.append({
                "file_id": fname,
                "file_path": str(fpath.as_posix()),
                "sha256": sha,
                "sample_rate_hz": rate,
                "channels": channels,
                "duration_seconds": dur
            })
        return entries

    manifest = {
        "schema_version": "1.0",
        "project": "Aryntra Avni V3.0 S2 Real Identity & Expression Evaluation",
        "evaluation_purpose": "Operating envelope characterization of synthetic identity retention under acoustic expression modulation",
        "enrolled_speakers": [
            {
                "speaker_id": "SPK_A_AUTH",
                "name_pseudonym": "Authorized Alpha",
                "consent_reference_id": "CONSENT-V3-SPK-A",
                "provenance_notes": "Real authorized human voice sample for synthetic target identity derivation.",
                "intended_role": "identity_enrollment",
                "files": process_files(spk_a_files)
            },
            {
                "speaker_id": "SPK_B_AUTH",
                "name_pseudonym": "Authorized Beta",
                "consent_reference_id": "CONSENT-V3-SPK-B",
                "provenance_notes": "Real authorized human voice sample for source performance and speech content manifestation.",
                "intended_role": "source_performance",
                "files": process_files(spk_b_files)
            }
        ]
    }
    
    manifest_path = meta_dir / "consent_manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"[+] Successfully generated manifest at: {manifest_path}")
    print(f"    - Speaker A enrollment files: {len(spk_a_files)}")
    print(f"    - Speaker B performance files: {len(spk_b_files)}")

if __name__ == "__main__":
    build_manifest()