"""Unit tests for NeuralSpeakerExtractor."""

import math
import struct
import wave
import io
import pytest

from src.representation.neural_extractor import NeuralSpeakerExtractor, _bytes_to_embedding
from src.representation.base import ExtractionError


def _generate_synthetic_tone(freq: float, duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    n_frames = int(sample_rate * duration_sec)
    samples = [int(16000 * math.sin(2 * math.pi * freq * i / sample_rate)) for i in range(n_frames)]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(struct.pack(f"<{n_frames}h", *samples))
    return buf.getvalue()


def test_neural_extractor_properties():
    extractor = NeuralSpeakerExtractor()
    assert extractor.extractor_id == "neural_xvector"
    assert extractor.version == "1.0"
    assert extractor.embedding_dim == 512


def test_neural_extractor_empty_samples_raises():
    extractor = NeuralSpeakerExtractor()
    with pytest.raises(ExtractionError, match="No audio samples provided"):
        extractor.extract([])


def test_neural_extractor_invalid_audio_raises():
    extractor = NeuralSpeakerExtractor()
    with pytest.raises(ExtractionError, match="Cannot read audio"):
        extractor.extract([b"corrupted raw data"])


def test_neural_extractor_deterministic_and_similarity():
    extractor = NeuralSpeakerExtractor()
    audio_a = _generate_synthetic_tone(150.0)
    audio_b = _generate_synthetic_tone(350.0)

    # Determinism
    rep_a1 = extractor.extract([audio_a])
    rep_a2 = extractor.extract([audio_a])

    assert rep_a1.is_valid
    assert len(_bytes_to_embedding(rep_a1.data)) == 512

    sim_self = extractor.similarity(rep_a1, rep_a2)
    assert math.isclose(sim_self, 1.0, abs_tol=1e-4)

    # Separation
    rep_b = extractor.extract([audio_b])
    sim_diff = extractor.similarity(rep_a1, rep_b)
    # Different frequencies should be distinct, leading to similarity < 1.0
    assert sim_diff < 1.0
