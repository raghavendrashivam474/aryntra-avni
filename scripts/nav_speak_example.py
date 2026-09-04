"""Example script simulating NAV consuming Aryntra Avni Voice."""

import sys
from pathlib import Path

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import create_default_voice_capability, VoiceRequest, AvniVoiceError


def main():
    print("==================================================")
    print("Aryntra Avni — NAV Voice Integration Demo")
    print("==================================================")
    print("Initializing Avni Voice Capability for NAV...")
    voice = create_default_voice_capability()

    artifacts_dir = REPO_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)

    text_to_speak = "Greetings NAV. Aryntra Avni voice foundation is now fully operational."
    identity = "avni_default"

    print(f"\nRequesting speech: '{text_to_speak}'")
    print(f"Identity Target:    {identity}")

    try:
        response = voice.synthesize(
            VoiceRequest(
                text=text_to_speak,
                identity_id=identity,
                request_id="nav_sim_001",
            )
        )

        output_path = artifacts_dir / "nav_sample_output.mp3"
        with open(output_path, "wb") as f:
            f.write(response.audio_bytes)

        print("\n=== Synthesis Result ===")
        print(f"Status:             SUCCESS")
        print(f"Format:             {response.audio_format}")
        print(f"Sample Rate:        {response.sample_rate} Hz")
        print(f"Audio Size:         {len(response.audio_bytes)} bytes")
        print(f"Latency:            {response.metadata.get('generation_latency_sec')} s")
        print(f"Audio Output File:  {output_path.resolve()}")

    except AvniVoiceError as e:
        print(f"Speech generation failed: {e}")


if __name__ == "__main__":
    main()