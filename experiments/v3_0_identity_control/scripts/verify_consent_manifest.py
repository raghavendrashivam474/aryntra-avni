import json
import hashlib
from pathlib import Path

def calculate_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def verify_provenance() -> bool:
    manifest_path = Path("experiments/v3_0_identity_control/data/metadata/consent_manifest.json")
    if not manifest_path.exists():
        print(f"[-] CRITICAL ERROR: Consent manifest missing at {manifest_path}")
        return False
        
    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)
        
    print(f"[+] Loaded Manifest: {manifest.get('project')}")
    print(f"    Purpose: {manifest.get('evaluation_purpose')}\n")
    
    all_ok = True
    for speaker in manifest.get("enrolled_speakers", []):
        print(f"--- Speaker: {speaker['speaker_id']} ({speaker['name_pseudonym']}) ---")
        print(f"  Role:        {speaker['intended_role']}")
        print(f"  Consent Ref: {speaker['consent_reference_id']}")
        print(f"  Provenance:  {speaker['provenance_notes']}")
        
        for entry in speaker.get("files", []):
            fpath = Path(entry["file_path"])
            if not fpath.exists():
                print(f"  [-] MISSING FILE: {fpath}")
                all_ok = False
                continue
                
            actual_sha = calculate_sha256(fpath)
            expected_sha = entry.get("sha256", "")
            
            if actual_sha == expected_sha:
                print(f"  [+] {entry['file_id']} -> OK (Rate: {entry['sample_rate_hz']}Hz, Dur: {entry['duration_seconds']}s, SHA: {actual_sha[:12]}...)")
            else:
                print(f"  [-] CHECKSUM MISMATCH: {entry['file_id']}")
                print(f"      Expected: {expected_sha}")
                print(f"      Actual:   {actual_sha}")
                all_ok = False
        print()
        
    return all_ok

if __name__ == "__main__":
    success = verify_provenance()
    if not success:
        print("[!] Dataset verification FAILED. Pipeline halted.")
        exit(1)
    else:
        print("[+] VERIFICATION SUCCESSFUL: Dataset is authenticated and authorized for S2 evaluation.")
        exit(0)