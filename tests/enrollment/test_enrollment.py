"""Tests for S1 Enrollment pipeline."""

import struct
import wave
import tempfile
from pathlib import Path
from unittest import TestCase

from src.enrollment.contracts import (
    AudioSample,
    EnrollmentRequest,
    EnrollmentResult,
    EnrollmentStatus,
)
from src.enrollment.audio_validator import validate_audio_file
from src.enrollment.preprocessor import preprocess_audio
from src.enrollment.enrollment_service import EnrollmentService


def _create_test_wav(
    path: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    channels: int = 1,
    sample_width: int = 2,
) -> Path:
    """Helper: create a minimal valid WAV file for testing."""
    n_frames = int(sample_rate * duration_sec)
    # Generate silence (zeros)
    if sample_width == 2:
        frames = b"\x00\x00" * n_frames * channels
    else:
        frames = b"\x00" * n_frames * channels * sample_width

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(frames)
    return path


class TestAudioSampleValidation(TestCase):
    """Test AudioSample contract validation."""

    def test_valid_sample(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _create_test_wav(Path(tmpdir) / "test.wav")
            sample = AudioSample(
                file_path=wav_path,
                source_id="test_user",
                consent_granted=True,
            )
            errors = sample.validate()
            self.assertEqual(errors, [])

    def test_missing_file(self):
        sample = AudioSample(
            file_path=Path("/nonexistent/audio.wav"),
            source_id="test_user",
        )
        errors = sample.validate()
        self.assertTrue(any("not found" in e for e in errors))

    def test_no_consent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _create_test_wav(Path(tmpdir) / "test.wav")
            sample = AudioSample(
                file_path=wav_path,
                source_id="test_user",
                consent_granted=False,
            )
            errors = sample.validate()
            self.assertTrue(any("Consent" in e for e in errors))

    def test_empty_source_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = _create_test_wav(Path(tmpdir) / "test.wav")
            sample = AudioSample(
                file_path=wav_path,
                source_id="",
            )
            errors = sample.validate()
            self.assertTrue(any("source_id" in e for e in errors))


class TestEnrollmentRequestValidation(TestCase):
    """Test EnrollmentRequest contract validation."""

    def test_valid_request(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            samples = []
            for i in range(3):
                wav = _create_test_wav(Path(tmpdir) / f"sample_{i}.wav")
                samples.append(AudioSample(
                    file_path=wav,
                    source_id="user_1",
                ))
            req = EnrollmentRequest(
                identity_id="test_voice",
                samples=samples,
            )
            errors = req.validate()
            self.assertEqual(errors, [])

    def test_too_few_samples(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav = _create_test_wav(Path(tmpdir) / "one.wav")
            req = EnrollmentRequest(
                identity_id="test_voice",
                samples=[AudioSample(file_path=wav, source_id="u")],
            )
            errors = req.validate()
            self.assertTrue(any("Minimum 2" in e for e in errors))

    def test_empty_identity_id(self):
        req = EnrollmentRequest(identity_id="", samples=[])
        errors = req.validate()
        self.assertTrue(any("identity_id" in e for e in errors))


class TestAudioValidator(TestCase):
    """Test audio file validation."""

    def test_valid_wav(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav = _create_test_wav(Path(tmpdir) / "good.wav", duration_sec=3.0)
            is_valid, errors = validate_audio_file(wav)
            self.assertTrue(is_valid)
            self.assertEqual(errors, [])

    def test_too_short(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav = _create_test_wav(Path(tmpdir) / "short.wav", duration_sec=0.3)
            is_valid, errors = validate_audio_file(wav)
            self.assertFalse(is_valid)
            self.assertTrue(any("below minimum" in e for e in errors))

    def test_low_sample_rate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav = _create_test_wav(
                Path(tmpdir) / "lowrate.wav",
                sample_rate=8000,
                duration_sec=2.0,
            )
            is_valid, errors = validate_audio_file(wav)
            self.assertFalse(is_valid)
            self.assertTrue(any("Sample rate" in e for e in errors))

    def test_missing_file(self):
        is_valid, errors = validate_audio_file(Path("/no/such/file.wav"))
        self.assertFalse(is_valid)

    def test_nonexistent_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fake = Path(tmpdir) / "test.mp3"
            fake.write_bytes(b"fake audio data" * 100)
            is_valid, errors = validate_audio_file(fake)
            self.assertFalse(is_valid)
            self.assertTrue(any("Unsupported format" in e for e in errors))


class TestPreprocessor(TestCase):
    """Test audio preprocessing."""

    def test_preprocess_valid_wav(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav = _create_test_wav(Path(tmpdir) / "input.wav")
            result = preprocess_audio(wav)
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 44)  # more than WAV header

    def test_preprocess_stereo_to_mono(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            wav = _create_test_wav(
                Path(tmpdir) / "stereo.wav",
                channels=2,
            )
            result = preprocess_audio(wav)
            self.assertIsInstance(result, bytes)
            # Verify output is mono
            with wave.open(
                __import__("io").BytesIO(result), "rb"
            ) as wf:
                self.assertEqual(wf.getnchannels(), 1)


class TestEnrollmentService(TestCase):
    """Test the enrollment orchestrator."""

    def test_enroll_no_extractor_s1_boundary(self):
        """S1: enrollment validates and preprocesses without extractor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            samples = []
            for i in range(2):
                wav = _create_test_wav(Path(tmpdir) / f"s{i}.wav")
                samples.append(AudioSample(
                    file_path=wav,
                    source_id="test_user",
                ))
            req = EnrollmentRequest(
                identity_id="test_voice",
                samples=samples,
            )
            service = EnrollmentService(representation_extractor=None)
            result = service.enroll(req)

            self.assertTrue(result.is_success)
            self.assertEqual(result.identity_id, "test_voice")
            self.assertEqual(result.sample_count, 2)
            self.assertIsNone(result.representation_data)
            self.assertFalse(result.metadata["extractor_configured"])

    def test_enroll_with_mock_extractor(self):
        """S1: enrollment passes preprocessed audio to extractor."""
        def mock_extractor(audio_list):
            self.assertEqual(len(audio_list), 2)
            return b"mock_embedding_256dim", "mock-v1"

        with tempfile.TemporaryDirectory() as tmpdir:
            samples = []
            for i in range(2):
                wav = _create_test_wav(Path(tmpdir) / f"s{i}.wav")
                samples.append(AudioSample(
                    file_path=wav,
                    source_id="test_user",
                ))
            req = EnrollmentRequest(
                identity_id="test_voice",
                samples=samples,
            )
            service = EnrollmentService(representation_extractor=mock_extractor)
            result = service.enroll(req)

            self.assertTrue(result.is_success)
            self.assertEqual(result.representation_data, b"mock_embedding_256dim")
            self.assertEqual(result.representation_version, "mock-v1")

    def test_enroll_invalid_audio_rejected(self):
        """S1: enrollment rejects invalid audio cleanly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # One valid, one too short
            good = _create_test_wav(Path(tmpdir) / "good.wav", duration_sec=2.0)
            bad = _create_test_wav(Path(tmpdir) / "bad.wav", duration_sec=0.2)
            req = EnrollmentRequest(
                identity_id="test_voice",
                samples=[
                    AudioSample(file_path=good, source_id="u"),
                    AudioSample(file_path=bad, source_id="u"),
                ],
            )
            service = EnrollmentService()
            result = service.enroll(req)

            self.assertFalse(result.is_success)
            self.assertEqual(result.status, EnrollmentStatus.INVALID_AUDIO)

    def test_enroll_no_consent_rejected(self):
        """S1: enrollment rejects samples without consent."""
        with tempfile.TemporaryDirectory() as tmpdir:
            samples = []
            for i in range(2):
                wav = _create_test_wav(Path(tmpdir) / f"s{i}.wav")
                samples.append(AudioSample(
                    file_path=wav,
                    source_id="user",
                    consent_granted=False,
                ))
            req = EnrollmentRequest(
                identity_id="test_voice",
                samples=samples,
            )
            service = EnrollmentService()
            result = service.enroll(req)

            self.assertFalse(result.is_success)
