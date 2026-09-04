"""Unit tests for IdentityLoader and baseline identity configurations."""

import unittest
from pathlib import Path
from src.capabilities.voice.identity_loader import IdentityLoader
from src.contracts.errors import AvniVoiceError, VoiceErrorCode


class TestIdentityLoader(unittest.TestCase):

    def test_load_default_identities_directory(self):
        configs_dir = Path("configs/identities")
        identities = IdentityLoader.load_directory(configs_dir)

        self.assertGreaterEqual(len(identities), 2)
        id_map = {ident.identity_id: ident for ident in identities}

        self.assertIn("avni_default", id_map)
        self.assertEqual(id_map["avni_default"].renderer_id, "edge_tts")
        self.assertEqual(id_map["avni_default"].voice_configuration["voice"], "en-US-AriaNeural")

        self.assertIn("avni_guy", id_map)
        self.assertEqual(id_map["avni_guy"].renderer_id, "edge_tts")

    def test_invalid_identity_dict_missing_fields(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            IdentityLoader.load_from_dict({"renderer_id": "edge_tts"})
        self.assertEqual(ctx.exception.code, VoiceErrorCode.CONFIGURATION_FAILURE)

    def test_missing_file_raises_configuration_failure(self):
        with self.assertRaises(AvniVoiceError) as ctx:
            IdentityLoader.load_from_json_file("configs/identities/does_not_exist.json")
        self.assertEqual(ctx.exception.code, VoiceErrorCode.CONFIGURATION_FAILURE)


if __name__ == "__main__":
    unittest.main()