"""Contract tests for VoiceCapability using a deterministic FakeRenderer.

No real TTS engine is required.  These tests verify:
  - successful synthesis path
  - every VoiceErrorCode is raised under the correct condition
  - renderer exceptions are wrapped, never leaked raw
"""

import unittest

from src.contracts.voice import VoiceRequest, VoiceIdentity
from src.contracts.renderer import TTSRenderer, RenderResult
from src.contracts.errors import AvniVoiceError, VoiceErrorCode
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry
from src.capabilities.voice.capability import VoiceCapability


# ------------------------------------------------------------------ #
#  Fake renderer                                                       #
# ------------------------------------------------------------------ #

class FakeRenderer(TTSRenderer):
    """Deterministic stand-in — no audio engine required."""

    def __init__(
        self,
        rid: str = "fake_tts",
        available: bool = True,
        should_fail: bool = False,
    ):
        self._rid = rid
        self._available = available
        self._should_fail = should_fail

    @property
    def renderer_id(self) -> str:
        return self._rid

    def is_available(self) -> bool:
        return self._available

    def render(self, text, voice_config, context=None):
        if self._should_fail:
            raise RuntimeError("simulated engine crash")
        fake_audio = b"RIFF" + text.encode("utf-8")
        return RenderResult(
            audio_bytes=fake_audio,
            audio_format="wav",
            sample_rate=22050,
            duration_seconds=1.25,
            metadata={"voice_key": voice_config.get("voice_key", "default")},
        )


# ------------------------------------------------------------------ #
#  Tests                                                               #
# ------------------------------------------------------------------ #

class TestVoiceCapabilityContracts(unittest.TestCase):

    def setUp(self):
        self.ids = IdentityRegistry()
        self.rens = RendererRegistry()

        self.rens.register(FakeRenderer(rid="fake_tts"))
        self.ids.register(VoiceIdentity(
            identity_id="avni_default",
            renderer_id="fake_tts",
            voice_configuration={"voice_key": "v_01"},
            provenance={"source": "test"},
        ))

        self.cap = VoiceCapability(
            identity_registry=self.ids,
            renderer_registry=self.rens,
        )

    # ---- happy path ----

    def test_successful_synthesis(self):
        req = VoiceRequest(text="Hello NAV", identity_id="avni_default", request_id="r1")
        res = self.cap.synthesize(req)

        self.assertEqual(res.request_id, "r1")
        self.assertEqual(res.audio_format, "wav")
        self.assertEqual(res.sample_rate, 22050)
        self.assertGreater(len(res.audio_bytes), 0)
        self.assertEqual(res.metadata["identity_id"], "avni_default")
        self.assertEqual(res.metadata["renderer_id"], "fake_tts")
        self.assertIn("generation_latency_sec", res.metadata)

    # ---- INVALID_REQUEST ----

    def test_empty_text(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="", identity_id="avni_default"))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.INVALID_REQUEST)

    def test_whitespace_text(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="   ", identity_id="avni_default"))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.INVALID_REQUEST)

    def test_empty_identity_id(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="ok", identity_id=""))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.INVALID_REQUEST)

    # ---- UNKNOWN_IDENTITY ----

    def test_unknown_identity(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="ok", identity_id="ghost"))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.UNKNOWN_IDENTITY)

    # ---- RENDERER_UNAVAILABLE ----

    def test_unregistered_renderer(self):
        self.ids.register(VoiceIdentity(identity_id="orphan", renderer_id="no_such_renderer"))
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="ok", identity_id="orphan"))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.RENDERER_UNAVAILABLE)

    def test_offline_renderer(self):
        self.rens.register(FakeRenderer(rid="offline", available=False))
        self.ids.register(VoiceIdentity(identity_id="off_voice", renderer_id="offline"))
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="ok", identity_id="off_voice"))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.RENDERER_UNAVAILABLE)

    # ---- GENERATION_FAILURE ----

    def test_renderer_crash_wrapped(self):
        self.rens.register(FakeRenderer(rid="broken", should_fail=True))
        self.ids.register(VoiceIdentity(identity_id="brk_voice", renderer_id="broken"))
        with self.assertRaises(AvniVoiceError) as ctx:
            self.cap.synthesize(VoiceRequest(text="ok", identity_id="brk_voice"))
        self.assertEqual(ctx.exception.code, VoiceErrorCode.GENERATION_FAILURE)
        # raw RuntimeError must NOT be the public exception type
        self.assertNotIsInstance(ctx.exception, RuntimeError)


if __name__ == "__main__":
    unittest.main()