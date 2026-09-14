"""V3.0 S1 — Controlled Expression Manifestation Tests."""

import pytest
from src.contracts.expression import (
    ExpressionConfig,
    NEUTRAL_EXPRESSION,
    PITCH_SCALE_RANGE,
    RATE_SCALE_RANGE,
    ENERGY_SCALE_RANGE,
)
from src.contracts.voice import VoiceRequest


# ── ExpressionConfig Contract ──────────────────────────────

class TestExpressionConfigDefaults:
    def test_default_is_neutral(self):
        c = ExpressionConfig()
        assert c.is_neutral is True
        assert c.pitch_scale == 1.0
        assert c.rate_scale == 1.0
        assert c.energy_scale == 1.0

    def test_neutral_factory(self):
        assert ExpressionConfig.neutral().is_neutral is True

    def test_singleton_is_neutral(self):
        assert NEUTRAL_EXPRESSION.is_neutral is True


class TestExpressionConfigValidation:
    def test_valid_boundary_values(self):
        lo, hi = PITCH_SCALE_RANGE
        assert ExpressionConfig(pitch_scale=lo).pitch_scale == lo
        assert ExpressionConfig(pitch_scale=hi).pitch_scale == hi

    def test_pitch_too_low(self):
        with pytest.raises(ValueError, match="pitch_scale"):
            ExpressionConfig(pitch_scale=0.1)

    def test_pitch_too_high(self):
        with pytest.raises(ValueError, match="pitch_scale"):
            ExpressionConfig(pitch_scale=5.0)

    def test_rate_invalid(self):
        with pytest.raises(ValueError, match="rate_scale"):
            ExpressionConfig(rate_scale=0.0)

    def test_energy_invalid(self):
        with pytest.raises(ValueError, match="energy_scale"):
            ExpressionConfig(energy_scale=-1.0)

    def test_type_rejection(self):
        with pytest.raises(TypeError, match="pitch_scale"):
            ExpressionConfig(pitch_scale="high")

    def test_non_neutral_detected(self):
        assert ExpressionConfig(pitch_scale=1.1).is_neutral is False


class TestExpressionConfigImmutability:
    def test_frozen_pitch(self):
        c = ExpressionConfig()
        with pytest.raises(AttributeError):
            c.pitch_scale = 1.5

    def test_frozen_rate(self):
        c = ExpressionConfig()
        with pytest.raises(AttributeError):
            c.rate_scale = 0.8

    def test_frozen_energy(self):
        c = ExpressionConfig()
        with pytest.raises(AttributeError):
            c.energy_scale = 1.2


# ── VoiceRequest Backward Compatibility ────────────────────

class TestVoiceRequestBackwardCompat:
    def test_construction_without_expression(self):
        """V2.5 callers must continue to work unchanged."""
        req = VoiceRequest(text="Hello", identity_id="speaker_a")
        assert req.text == "Hello"
        assert req.identity_id == "speaker_a"

    def test_default_expression_is_neutral(self):
        req = VoiceRequest(text="Test", identity_id="speaker_a")
        assert hasattr(req, "expression")
        assert req.expression.is_neutral is True

    def test_explicit_expression(self):
        expr = ExpressionConfig(pitch_scale=1.1, rate_scale=0.95)
        req = VoiceRequest(text="Expressive", identity_id="speaker_a", expression=expr)
        assert req.expression.pitch_scale == 1.1
        assert req.expression.rate_scale == 0.95
        assert req.expression.energy_scale == 1.0

    def test_neutral_explicit_equals_implicit(self):
        r1 = VoiceRequest(text="Same", identity_id="a")
        r2 = VoiceRequest(text="Same", identity_id="a", expression=NEUTRAL_EXPRESSION)
        assert r1.expression == r2.expression


# ── Capability Context Propagation ─────────────────────────

class TestExpressionContextPropagation:
    def test_merge_neutral_returns_original_context(self):
        from src.capabilities.voice.capability import VoiceCapability
        ctx = {"some_key": "value"}
        result = VoiceCapability._merge_expression_context(ctx, NEUTRAL_EXPRESSION)
        assert result == ctx
        assert "expression" not in result

    def test_merge_none_expression_returns_original(self):
        from src.capabilities.voice.capability import VoiceCapability
        ctx = {"some_key": "value"}
        result = VoiceCapability._merge_expression_context(ctx, None)
        assert result == ctx

    def test_merge_active_expression_injects_dict(self):
        from src.capabilities.voice.capability import VoiceCapability
        expr = ExpressionConfig(pitch_scale=1.2, rate_scale=0.9, energy_scale=1.1)
        result = VoiceCapability._merge_expression_context({}, expr)
        assert "expression" in result
        assert result["expression"]["pitch_scale"] == 1.2
        assert result["expression"]["rate_scale"] == 0.9
        assert result["expression"]["energy_scale"] == 1.1

    def test_merge_preserves_existing_context_keys(self):
        from src.capabilities.voice.capability import VoiceCapability
        expr = ExpressionConfig(pitch_scale=1.1)
        ctx = {"nav_session": "abc123", "language": "en"}
        result = VoiceCapability._merge_expression_context(ctx, expr)
        assert result["nav_session"] == "abc123"
        assert result["language"] == "en"
        assert "expression" in result

    def test_merge_with_none_context_creates_dict(self):
        from src.capabilities.voice.capability import VoiceCapability
        expr = ExpressionConfig(pitch_scale=1.1)
        result = VoiceCapability._merge_expression_context(None, expr)
        assert result is not None
        assert "expression" in result
