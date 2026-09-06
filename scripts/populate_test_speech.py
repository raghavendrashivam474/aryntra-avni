"""Generate authorized voice dataset for V2.0 Evaluation.

Uses EdgeTTS neural voices decoded via soundfile and resampled via scipy
to produce 16kHz 16-bit mono PCM WAVs with distinct phonetic content,
sentence lengths, and prosody for Speaker A (Male) and Speaker B (Female).
"""

import asyncio
import io
import numpy as np
import soundfile as sf
from scipy.signal import resample
from pathlib import Path
import edge_tts

# Text prompts for Enrollment (different from evaluation)
ENROLLMENT_TEXTS = {
    "speaker_a": [
        "Hello, my name is Alex. I am recording my voice for the Avni identity research baseline.",
        "The quick brown fox jumps over the lazy dog near the riverbank on a sunny afternoon.",
    ],
    "speaker_b": [
        "Hi there, I am Sarah. This recording authorizes the creation of my persistent voice identity profile.",
        "Quantum computing and artificial intelligence are rapidly reshaping modern computational science.",
    ],
}

# Text prompts for Evaluation (held-out, different text and length)
EVALUATION_TEXTS = {
    "speaker_a": [
        "Today's weather forecast calls for clear blue skies with a gentle breeze from the northwest.",
        "Could you please review the latest laboratory results and verify the experimental parameters?",
        "Navigating through complex systems requires clear boundaries, strong contracts, and disciplined architecture.",
    ],
    "speaker_b": [
        "We observed significant improvements in perceptual naturalness after tuning the vocoder parameters.",
        "Deep learning models require careful validation against real-world datasets before deployment.",
        "Let us examine how well the persistent voice representation retains distinct speaker identity characteristics.",
    ],
}

VOICE_MAP = {
    "speaker_a": "en-US-GuyNeural",
    "speaker_b": "en-US-JennyNeural",
}


async def generate_sample(text: str, voice: str, dest_path: Path):
    print(f"Generating: {dest_path.name} ({voice})...")
    communicate = edge_tts.Communicate(text=text, voice=voice)
    mp3_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            mp3_data += chunk["data"]

    # Decode MP3 using soundfile
    audio_data, src_sr = sf.read(io.BytesIO(mp3_data))

    # Convert to mono if stereo
    if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
        audio_data = np.mean(audio_data, axis=1)

    # Resample to 16000 Hz using scipy
    target_sr = 16000
    if src_sr != target_sr:
        num_samples = int(len(audio_data) * target_sr / src_sr)
        audio_data = resample(audio_data, num_samples)

    # Clip to float [-1.0, 1.0] and write as 16-bit PCM WAV
    audio_data = np.clip(audio_data, -1.0, 1.0)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dest_path), audio_data, target_sr, subtype="PCM_16", format="WAV")

    duration = len(audio_data) / target_sr
    print(f"  Saved {dest_path.name} (16kHz mono WAV, duration: {duration:.2f}s)")


async def main_async():
    base_dir = Path(__file__).resolve().parent.parent / "data" / "evaluation"

    print("=== Generating V2.0 Evaluation Voice Dataset ===")

    for speaker_id, voice in VOICE_MAP.items():
        print(f"\n--- {speaker_id.upper()} ({voice}) ---")

        # Enrollment
        for idx, text in enumerate(ENROLLMENT_TEXTS[speaker_id], 1):
            dest = base_dir / speaker_id / "enrollment" / f"sample_{idx}.wav"
            await generate_sample(text, voice, dest)

        # Evaluation
        for idx, text in enumerate(EVALUATION_TEXTS[speaker_id], 1):
            dest = base_dir / speaker_id / "evaluation" / f"eval_{idx}.wav"
            await generate_sample(text, voice, dest)

    print("\n[SUCCESS] Dataset generated successfully!")


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
