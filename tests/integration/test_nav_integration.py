"""Integration tests verifying NAV consumption flow."""

import unittest
from src import create_default_voice_capability, VoiceRequest, AvniVoiceError, VoiceErrorCode


class TestNAVIntegration(unittest.TestCase):

    def setUp(self):
        self.voice = create_default_voice_capability()

    def test_nav_can_synthesize_with_default_identity(self):
        req = VoiceRequest(
            text="NAV integration test with default identity.",
            identity_id="avni_default",
            request_id="nav_test_1",
        )
        res = self.voice.synthesize(req)
        self.assertEqual(res.request_id, "nav_test_1")
        self.assertGreater(len(res.audio_bytes), 1000)
        self.assertEqual(res.audio_format, "mp3")
        self.assertEqual(res.metadata["identity_id"], "avni_default")

    def test_nav_can_switch_to_alternate_identity(self):
        req = VoiceRequest(
            text="NAV integration test with alternate guy identity.",
            identity_id="avni_guy",
            request_id="nav_test_2",
        )
        res = self.voice.synthesize(req)
        self.assertEqual(res.request_id, "nav_test_2")
        self.assertEqual(res.metadata["identity_id"], "avni_guy")

    def test_nav_receives_structured_error_on_invalid_identity(self):
        req = VoiceRequest(
            text="Invalid identity request",
            identity_id="non_existent_persona",
        )
        with self.assertRaises(AvniVoiceError) as ctx:
            self.voice.synthesize(req)
        self.assertEqual(ctx.exception.code, VoiceErrorCode.UNKNOWN_IDENTITY)


if __name__ == "__main__":
    unittest.main()