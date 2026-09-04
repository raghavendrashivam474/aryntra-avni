import io
import wave
import pytest
from src.adapters.tts.piper_adapter import PiperTTSAdapter
from src.adapters.tts.edge_tts_adapter import EdgeTTSAdapter


def test_piper_audio_wav_structure():
    adapter = PiperTTSAdapter()
    result = adapter.render("Testing WAV header validation in Avni.", {})

    assert result.audio_format == "wav"
    assert len(result.audio_bytes) > 44

    # Validate using standard library wave reader
    with wave.open(io.BytesIO(result.audio_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2  # 16-bit
        assert wf.getframerate() == 22050
        n_frames = wf.getnframes()
        assert n_frames > 0


def test_edge_tts_audio_structure():
    adapter = EdgeTTSAdapter()
    result = adapter.render("Testing MP3 stream validation in Avni.", {})

    assert result.audio_format == "mp3"
    assert len(result.audio_bytes) > 1000
    # MP3 frames typically start with sync word (0xFF 0xFB/0xF3/0xF2) or ID3 tag (0x49 0x44 0x33)
    header = result.audio_bytes[:3]
    is_mp3_sync = result.audio_bytes[0] == 0xFF and (result.audio_bytes[1] & 0xE0) == 0xE0
    is_id3 = header == b"ID3"
    assert is_mp3_sync or is_id3