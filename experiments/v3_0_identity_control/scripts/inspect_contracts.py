from pathlib import Path

def dump_file_segment(filepath, keyword, num_lines=25):
    print(f"\n--- {filepath} (around '{keyword}') ---")
    p = Path(filepath)
    if not p.exists():
        print("FILE NOT FOUND")
        return
    lines = p.read_text(encoding='utf-8').splitlines()
    for idx, line in enumerate(lines):
        if keyword in line:
            start = max(0, idx - 2)
            end = min(len(lines), idx + num_lines)
            for i in range(start, end):
                print(f"{i+1:4d}: {lines[i]}")
            return

dump_file_segment("src/contracts/renderer.py", "class VoiceConverter")
dump_file_segment("src/adapters/voice_conversion/acoustic_vc_adapter.py", "converter_id")
dump_file_segment("src/capabilities/voice/registry.py", "class ConverterRegistry")
dump_file_segment("tests/adapters/voice_conversion/test_converters.py", "test_speecht5_vc_properties")