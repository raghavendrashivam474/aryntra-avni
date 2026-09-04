import pytest
from pathlib import Path
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.adapters.tts.piper_adapter import PiperTTSAdapter


def test_piper_adapter_properties():
    adapter = PiperTTSAdapter()
    assert adapter.renderer_id == "piper"
    assert adapter.is_available() is True


def test_piper_adapter_render_success():
    adapter = PiperTTSAdapter()
    result = adapter.render("Hello world from offline Piper.", {})

    assert result.audio_format == "wav"
    assert result.sample_rate == 22050
    assert len(result.audio_bytes) > 1000
    assert result.metadata["engine"] == "piper"
    # WAV header validation (starts with 'RIFF' and has 'WAVE')
    assert result.audio_bytes[:4] == b"RIFF"
    assert result.audio_bytes[8:12] == b"WAVE"


def test_piper_adapter_missing_model_raises_configuration_failure():
    adapter = PiperTTSAdapter()
    with pytest.raises(AvniVoiceError) as exc_info:
        adapter.render(
            "Hello",
            {"model_path": "non_existent_model.onnx"},
        )
    assert exc_info.value.code == VoiceErrorCode.CONFIGURATION_FAILURE
