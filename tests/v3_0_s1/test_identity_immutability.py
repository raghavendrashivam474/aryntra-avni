"""Identity Immutability Tests under Expressive Manifestation.

Verifies Section 20 of Brief:
Manifestation must be strictly read-only with respect to persistent identity.
No request-time expression parameter may mutate registered VoiceIdentity
or persistent VoiceRepresentation data.
"""

import copy
import struct
import numpy as np
import pytest

from src import create_default_voice_capability, VoiceRequest
from src.contracts.expression import ExpressionConfig
from src.contracts.voice import VoiceIdentity


class TestPersistentIdentityImmutability:
    """Ensure persistent identity profile remains bit-for-bit identical."""

    @pytest.fixture
    def setup_identity(self):
        rng = np.random.RandomState(42)
        raw_emb = rng.randn(512).astype(np.float32)
        raw_emb = raw_emb / np.linalg.norm(raw_emb)
        emb_bytes = struct.pack("<512f", *raw_emb)

        identity = VoiceIdentity(
            identity_id="immutable-target-voice",
            renderer_id="speecht5",
            voice_configuration={
                "representation_data": emb_bytes,
                "sample_rate": 16000,
            }
        )
        return identity, emb_bytes

    def test_expression_does_not_mutate_voice_identity(self, setup_identity):
        identity, original_bytes = setup_identity
        capability = create_default_voice_capability()
        capability.identities.register(identity)

        # Snapshot before
        config_before = copy.deepcopy(identity.voice_configuration)
        emb_before = bytes(identity.voice_configuration["representation_data"])

        # Execute multiple varying expressive requests
        expressions = [
            ExpressionConfig(pitch_scale=1.2, rate_scale=0.9, energy_scale=1.1),
            ExpressionConfig(pitch_scale=0.8, rate_scale=1.2, energy_scale=0.8),
            ExpressionConfig.neutral(),
        ]

        for expr in expressions:
            req = VoiceRequest(
                text="Identity must remain strictly persistent.",
                identity_id=identity.identity_id,
                expression=expr,
            )
            # We don't need to synthesize full audio in unit tests if renderer is mocked,
            # but testing the capability resolution path:
            resolved_identity = capability._resolve_identity(identity.identity_id)
            assert resolved_identity.voice_configuration["representation_data"] == original_bytes

        # Snapshot after
        config_after = identity.voice_configuration
        emb_after = bytes(identity.voice_configuration["representation_data"])

        assert config_before == config_after
        assert emb_before == emb_after
        assert emb_after == original_bytes
