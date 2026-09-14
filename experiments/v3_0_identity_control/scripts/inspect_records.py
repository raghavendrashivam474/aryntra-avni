import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from src.profiles.voice_profile import ConsentRecord, ProvenanceRecord

def print_class_fields(cls):
    print(f"\nClass: {cls.__name__}")
    try:
        sig = inspect.signature(cls.__init__)
        print(f"  Init Signature: {sig}")
        for param_name, param in sig.parameters.items():
            if param_name != 'self':
                print(f"    - {param_name}: {param.annotation} (default={param.default})")
    except Exception as e:
         print(f"  Error reading fields: {e}")

print_class_fields(ConsentRecord)
print_class_fields(ProvenanceRecord)