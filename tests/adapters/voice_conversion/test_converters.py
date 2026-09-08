"""Unit tests for Voice Conversion adapters (Acoustic and SpeechT5)."""

import io
import struct
import wave
import pytest
import numpy as np

from src.contracts.errors import AvniVoiceError
from src.adapters.voice_conversion.acoustic_vc_adapter import AcousticVCAdapter
from src.adapters.voice_conversion.speecht5_vc_adapter import SpeechT5VCAdapter


def create_mock_wav_bytes(duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Helper to generate standard 16-bit PCM mono WAV bytes."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # A simple 440Hz sine wave tone
    samples = (np.sin(2 * np.pi * 440.0 * t) * 32767).astype(np.int16)
    
    out_buf = io.BytesIO()
    with wave.open(out_buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.tobytes())
    return out_buf.getvalue()


def create_mock_embedding_bytes(dim: int = 512) -> bytes:
    """Helper to generate a serialized float array of dim elements."""
    floats = [0.1 * (i % 5) for i in range(dim)]
    return struct.pack(f"<{dim}f", *floats)


def test_acoustic_vc_properties():
    adapter = AcousticVCAdapter()
    assert adapter.converter_id == "acoustic_vc"
    assert adapter.is_available() is True


def test_acoustic_vc_successful_conversion():
    adapter = AcousticVCAdapter()
    source_audio = create_mock_wav_bytes(duration_sec=1.0, sample_rate=16000)
    rep_data = create_mock_embedding_bytes(dim=512)
    
    result = adapter.convert(
        source_audio_bytes=source_audio,
        voice_config={"representation_data": rep_data}
    )
    
    assert result.audio_bytes is not None
    assert len(result.audio_bytes) > 100
    assert result.audio_format == "wav"
    assert result.sample_rate == 16000
    assert abs(result.duration_seconds - 1.0) < 0.1
    assert "engine" in result.metadata
    assert result.metadata["engine"] == "acoustic_vc"


def test_acoustic_vc_handles_missing_embedding_by_defaulting():
    adapter = AcousticVCAdapter()
    source_audio = create_mock_wav_bytes(duration_sec=0.5, sample_rate=16000)
    
    # Acoustic converter should survive missing embedding by using its default shift
    result = adapter.convert(
        source_audio_bytes=source_audio,
        voice_config={}
    )
    assert result.audio_bytes is not None
    assert result.metadata["engine"] == "acoustic_vc"


def test_speecht5_vc_properties():
    adapter = SpeechT5VCAdapter()
    assert adapter.converter_id == "speecht5_vc"


def test_speecht5_vc_missing_embedding_raises():
    adapter = SpeechT5VCAdapter()
    source_audio = create_mock_wav_bytes(duration_sec=0.5, sample_rate=16000)
    
    with pytest.raises(AvniVoiceError) as exc_info:
        adapter.convert(source_audio_bytes=source_audio, voice_config={})
    assert "requires target voice representation data" in exc_info.value.message


def test_speecht5_vc_invalid_embedding_dimension_raises():
    adapter = SpeechT5VCAdapter()
    source_audio = create_mock_wav_bytes(duration_sec=0.5, sample_rate=16000)
    bad_rep = create_mock_embedding_bytes(dim=128)  # SpeechT5 requires 512
    
    with pytest.raises(AvniVoiceError) as exc_info:
        adapter.convert(
            source_audio_bytes=source_audio,
            voice_config={"representation_data": bad_rep}
        )
    assert "512-dimensional speaker embeddings" in exc_info.value.message
