"""Unit tests for V2.0 evaluation harness.

Tests the harness infrastructure using synthetic audio,
NOT real human speech. Real speech evaluation is done
through the experiment scripts.
"""

import io
import math
import struct
import tempfile
import wave
from pathlib import Path

import pytest

from experiments.voice.v2_0_harness import (
    ExperimentConfig,
    V2EvaluationHarness,
    get_wav_info,
    hash_audio,
    resample_wav_to_16k,
)


def _make_wav(freq: float = 440.0, duration: float = 1.0,
              sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Create a synthetic WAV for testing."""
    n_frames = int(sample_rate * duration)
    samples = [int(16000 * math.sin(2 * math.pi * freq * i / sample_rate))
               for i in range(n_frames)]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        if channels == 2:
            stereo = []
            for s in samples:
                stereo.extend([s, s])
            wf.writeframes(struct.pack(f"<{len(stereo)}h", *stereo))
        else:
            wf.writeframes(struct.pack(f"<{n_frames}h", *samples))
    return buf.getvalue()


def test_get_wav_info():
    wav = _make_wav(freq=440, duration=2.0, sample_rate=16000)
    info = get_wav_info(wav)
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    assert info["duration_seconds"] == 2.0


def test_hash_audio_deterministic():
    wav = _make_wav()
    h1 = hash_audio(wav)
    h2 = hash_audio(wav)
    assert h1 == h2
    assert len(h1) == 16


def test_resample_16k_passthrough():
    """16kHz mono should pass through unchanged in structure."""
    wav = _make_wav(sample_rate=16000, channels=1)
    result = resample_wav_to_16k(wav)
    info = get_wav_info(result)
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1


def test_resample_44k_to_16k():
    """44.1kHz should be resampled to 16kHz."""
    wav = _make_wav(sample_rate=44100, channels=1, duration=1.0)
    result = resample_wav_to_16k(wav)
    info = get_wav_info(result)
    assert info["sample_rate"] == 16000
    assert info["channels"] == 1
    # Duration should be approximately preserved
    assert abs(info["duration_seconds"] - 1.0) < 0.1


def test_resample_stereo_to_mono():
    """Stereo should be converted to mono."""
    wav = _make_wav(sample_rate=16000, channels=2)
    result = resample_wav_to_16k(wav)
    info = get_wav_info(result)
    assert info["channels"] == 1


def test_experiment_config_defaults():
    config = ExperimentConfig(
        experiment_id="test",
        data_dir="/tmp/data",
        output_dir="/tmp/output",
    )
    assert len(config.speakers) == 2
    assert len(config.test_texts) == 5


def test_harness_discover_empty():
    """Harness should handle missing data gracefully."""
    with tempfile.TemporaryDirectory() as tmp:
        config = ExperimentConfig(
            experiment_id="test_empty",
            data_dir=tmp,
            output_dir=str(Path(tmp) / "output"),
        )
        harness = V2EvaluationHarness(config)
        files = harness.discover_speaker_files("speaker_a")
        assert files["enrollment"] == []
        assert files["evaluation"] == []


def test_harness_discover_with_files():
    """Harness should find WAV files in correct directories."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        enroll_dir = tmp_path / "speaker_a" / "enrollment"
        eval_dir = tmp_path / "speaker_a" / "evaluation"
        enroll_dir.mkdir(parents=True)
        eval_dir.mkdir(parents=True)

        # Create dummy WAV files
        for i in range(2):
            (enroll_dir / f"sample_{i}.wav").write_bytes(_make_wav())
        for i in range(3):
            (eval_dir / f"eval_{i}.wav").write_bytes(_make_wav())

        config = ExperimentConfig(
            experiment_id="test_discover",
            data_dir=str(tmp_path),
            output_dir=str(tmp_path / "output"),
        )
        harness = V2EvaluationHarness(config)
        files = harness.discover_speaker_files("speaker_a")
        assert len(files["enrollment"]) == 2
        assert len(files["evaluation"]) == 3
