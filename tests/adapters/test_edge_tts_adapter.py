"""Smoke and Unit tests for EdgeTTSAdapter."""

import unittest
from src.adapters.tts.edge_tts_adapter import EdgeTTSAdapter
from src.contracts.voice import VoiceRequest, VoiceIdentity
from src.capabilities.voice.registry import IdentityRegistry, RendererRegistry
from src.capabilities.voice.capability import VoiceCapability


class TestEdgeTTSAdapter(unittest.TestCase):

    def setUp(self):
        self.adapter = EdgeTTSAdapter()

    def test_adapter_properties(self):
        self.assertEqual(self.adapter.renderer_id, "edge_tts")
        self.assertTrue(self.adapter.is_available())

    def test_live_synthesis_smoke(self):
        """End-to-end integration smoke test with real speech generation."""
        identities = IdentityRegistry()
        renderers = RendererRegistry()

        renderers.register(self.adapter)
        identities.register(
            VoiceIdentity(
                identity_id="avni_aria",
                renderer_id="edge_tts",
                voice_configuration={"voice": "en-US-AriaNeural"},
            )
        )

        cap = VoiceCapability(identity_registry=identities, renderer_registry=renderers)

        req = VoiceRequest(
            text="Aryntra Avni voice foundation is active.",
            identity_id="avni_aria",
            request_id="smoke_001",
        )

        resp = cap.synthesize(req)

        self.assertEqual(resp.request_id, "smoke_001")
        self.assertEqual(resp.audio_format, "mp3")
        self.assertGreater(len(resp.audio_bytes), 1000)
        self.assertEqual(resp.metadata["renderer_id"], "edge_tts")
        self.assertEqual(resp.metadata["voice"], "en-US-AriaNeural")
        self.assertIn("generation_latency_sec", resp.metadata)


if __name__ == "__main__":
    unittest.main()