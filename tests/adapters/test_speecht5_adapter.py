"""Unit tests for SpeechT5TTSAdapter."""

import struct
import pytest

from src.adapters.tts.speecht5_adapter import SpeechT5TTSAdapter
from src.contracts.errors import AvniVoiceError, VoiceErrorCode


def test_speecht5_adapter_properties():
    adapter = SpeechT5TTSAdapter()
    assert adapter.renderer_id == "speecht5"
    assert adapter.is_available() is True


def test_speecht5_adapter_missing_embedding_raises():
    adapter = SpeechT5TTSAdapter()
    with pytest.raises(AvniVoiceError) as exc_info:
        adapter.render("Hello world", voice_config={})
    assert exc_info.value.code == VoiceErrorCode.INVALID_REQUEST
    assert "requires raw voice representation data" in exc_info.value.message


def test_speecht5_adapter_invalid_embedding_dimension_raises():
    adapter = SpeechT5TTSAdapter()
    # Provide 8-dim vector instead of 512-dim
    dummy_8dim = struct.pack("<8f", *[0.1] * 8)
    with pytest.raises(AvniVoiceError) as exc_info:
        adapter.render("Hello world", voice_config={"representation_data": dummy_8dim})
    assert exc_info.value.code == VoiceErrorCode.CONFIGURATION_FAILURE
    assert "requires 512-dimensional speaker embeddings" in exc_info.value.message
