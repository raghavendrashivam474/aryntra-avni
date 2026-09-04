"""End-to-end test: Enrollment -> Representation extraction."""

import math
import struct
import wave
import tempfile
from pathlib import Path
from unittest import TestCase

from src.enrollment.contracts import AudioSample, EnrollmentRequest
from src.enrollment.enrollment_service import EnrollmentService
from src.representation.acoustic_extractor import AcousticFeatureExtractor


def _create_tone_wav(
    path: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
) -> Path:
    """Create a WAV file with a sine tone."""
    n_frames = int(sample_rate * duration_sec)
    samples = [
        int(16000 * math.sin(2 * math.pi * frequency * i / sample_rate))
        for i in range(n_frames)
    ]
    frames = struct.pack(f"<{n_frames}h", *samples)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path


class TestEnrollmentWithRepresentation(TestCase):
    """Test full enrollment pipeline with acoustic feature extractor."""

    def test_enroll_with_acoustic_extractor(self):
        """Enrollment produces a real representation via AcousticFeatureExtractor."""
        extractor = AcousticFeatureExtractor()
        service = EnrollmentService(representation_extractor=extractor)

        with tempfile.TemporaryDirectory() as tmpdir:
            samples = []
            for i, freq in enumerate([440.0, 445.0, 438.0]):
                wav = _create_tone_wav(
                    Path(tmpdir) / f"sample_{i}.wav",
                    frequency=freq,
                )
                samples.append(AudioSample(
                    file_path=wav,
                    source_id="test_speaker",
                    consent_granted=True,
                ))

            request = EnrollmentRequest(
                identity_id="test_voice_v1",
                samples=samples,
                consent_metadata={"authorized_by": "test"},
                provenance={"test": True},
            )

            result = service.enroll(request)

            self.assertTrue(result.is_success)
            self.assertIsNotNone(result.representation_data)
            self.assertEqual(result.representation_version, "1.0")
            self.assertEqual(len(result.representation_data), 64)
            self.assertTrue(result.metadata["extractor_configured"])
            self.assertIn("representation", result.metadata)

    def test_enroll_deterministic(self):
        """Same recordings produce identical representations."""
        extractor = AcousticFeatureExtractor()
        service = EnrollmentService(representation_extractor=extractor)

        with tempfile.TemporaryDirectory() as tmpdir:
            samples = []
            for i in range(2):
                wav = _create_tone_wav(
                    Path(tmpdir) / f"s{i}.wav", frequency=880.0,
                )
                samples.append(AudioSample(
                    file_path=wav, source_id="u",
                ))

            req = EnrollmentRequest(identity_id="v", samples=samples)
            r1 = service.enroll(req)
            r2 = service.enroll(req)

            self.assertEqual(r1.representation_data, r2.representation_data)
