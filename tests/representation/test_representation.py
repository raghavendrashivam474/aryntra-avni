"""Tests for S2 Representation layer."""

import math
import struct
import wave
import tempfile
from io import BytesIO
from pathlib import Path
from unittest import TestCase

from src.representation.base import (
    ExtractionError,
    VoiceRepresentation,
)
from src.representation.acoustic_extractor import AcousticFeatureExtractor


def _make_wav_bytes(
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
) -> bytes:
    """Create a WAV byte stream with a sine tone."""
    n_frames = int(sample_rate * duration_sec)
    samples = []
    for i in range(n_frames):
        val = int(16000 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(val)
    frames = struct.pack(f"<{n_frames}h", *samples)

    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return buf.getvalue()


class TestVoiceRepresentation(TestCase):
    """Test the VoiceRepresentation data contract."""

    def test_valid_representation(self):
        rep = VoiceRepresentation(
            representation_id="test_v1",
            version="1.0",
            data=b"\x00" * 40,
        )
        self.assertTrue(rep.is_valid)

    def test_invalid_empty_data(self):
        rep = VoiceRepresentation(
            representation_id="test_v1",
            version="1.0",
            data=b"",
        )
        self.assertFalse(rep.is_valid)

    def test_invalid_empty_id(self):
        rep = VoiceRepresentation(
            representation_id="",
            version="1.0",
            data=b"\x00" * 40,
        )
        self.assertFalse(rep.is_valid)


class TestAcousticFeatureExtractor(TestCase):
    """Test the acoustic feature extractor."""

    def setUp(self):
        self.extractor = AcousticFeatureExtractor()

    def test_extractor_properties(self):
        self.assertEqual(self.extractor.extractor_id, "acoustic_stats")
        self.assertEqual(self.extractor.version, "1.0")

    def test_extract_single_sample(self):
        audio = _make_wav_bytes(duration_sec=2.0, frequency=440.0)
        rep = self.extractor.extract([audio])

        self.assertTrue(rep.is_valid)
        self.assertEqual(rep.version, "1.0")
        self.assertEqual(len(rep.data), 40)  # 5 doubles × 8 bytes
        self.assertIn("features", rep.metadata)

    def test_extract_multiple_samples(self):
        audio1 = _make_wav_bytes(duration_sec=2.0, frequency=440.0)
        audio2 = _make_wav_bytes(duration_sec=2.5, frequency=440.0)
        audio3 = _make_wav_bytes(duration_sec=1.5, frequency=440.0)

        rep = self.extractor.extract([audio1, audio2, audio3])

        self.assertTrue(rep.is_valid)
        self.assertEqual(rep.metadata["sample_count"], 3)

    def test_extract_empty_raises(self):
        with self.assertRaises(ExtractionError):
            self.extractor.extract([])

    def test_deterministic_extraction(self):
        """Same input must produce identical representation."""
        audio = _make_wav_bytes(duration_sec=2.0, frequency=880.0)
        rep1 = self.extractor.extract([audio])
        rep2 = self.extractor.extract([audio])

        self.assertEqual(rep1.data, rep2.data)

    def test_different_voices_different_representations(self):
        """Different frequencies should produce different features."""
        low = _make_wav_bytes(frequency=200.0)
        high = _make_wav_bytes(frequency=2000.0)

        rep_low = self.extractor.extract([low])
        rep_high = self.extractor.extract([high])

        self.assertNotEqual(rep_low.data, rep_high.data)

    def test_similarity_identical(self):
        audio = _make_wav_bytes(frequency=440.0)
        rep = self.extractor.extract([audio])
        sim = self.extractor.similarity(rep, rep)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_similarity_different(self):
        low = _make_wav_bytes(frequency=200.0)
        high = _make_wav_bytes(frequency=4000.0)
        rep_low = self.extractor.extract([low])
        rep_high = self.extractor.extract([high])
        sim = self.extractor.similarity(rep_low, rep_high)
        self.assertLess(sim, 1.0)
        self.assertGreaterEqual(sim, 0.0)

    def test_similarity_version_mismatch(self):
        rep_a = VoiceRepresentation("a", "1.0", b"\x00" * 40)
        rep_b = VoiceRepresentation("b", "2.0", b"\x00" * 40)
        with self.assertRaises(ExtractionError):
            self.extractor.similarity(rep_a, rep_b)

    def test_feature_values_reasonable(self):
        """Verify extracted features are in expected ranges."""
        audio = _make_wav_bytes(frequency=440.0, duration_sec=2.0)
        rep = self.extractor.extract([audio])
        feats = rep.metadata["features"]

        # Mean of a sine wave should be near zero
        self.assertAlmostEqual(feats["mean_amplitude"], 0.0, places=2)
        # RMS of a sine wave ≈ amplitude / sqrt(2)
        self.assertGreater(feats["rms_energy"], 0.0)
        # ZCR should be positive
        self.assertGreater(feats["zero_crossing_rate"], 0.0)
        # Spectral centroid should be positive
        self.assertGreater(feats["spectral_centroid"], 0.0)
