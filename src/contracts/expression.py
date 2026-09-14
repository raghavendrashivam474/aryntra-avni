"""
Controlled Expression Manifestation Configuration.

ExpressionConfig represents manifestation-time expression intent.
It is explicitly NOT part of persistent Voice Identity.
"""
from __future__ import annotations
from dataclasses import dataclass, field

PITCH_SCALE_RANGE = (0.5, 2.0)
RATE_SCALE_RANGE = (0.5, 2.0)
ENERGY_SCALE_RANGE = (0.5, 2.0)

@dataclass(frozen=True)
class ExpressionConfig:
    pitch_scale: float = 1.0
    rate_scale: float = 1.0
    energy_scale: float = 1.0

    def __post_init__(self) -> None:
        for name, value, (lo, hi) in [
            ("pitch_scale", self.pitch_scale, PITCH_SCALE_RANGE),
            ("rate_scale", self.rate_scale, RATE_SCALE_RANGE),
            ("energy_scale", self.energy_scale, ENERGY_SCALE_RANGE),
        ]:
            if not isinstance(value, (int, float)):
                raise TypeError(f"{name} must be numeric, got {type(value).__name__}")
            if not (lo <= float(value) <= hi):
                raise ValueError(f"{name}={value} outside valid range [{lo}, {hi}]")

    @property
    def is_neutral(self) -> bool:
        return (
            self.pitch_scale == 1.0
            and self.rate_scale == 1.0
            and self.energy_scale == 1.0
        )

    @classmethod
    def neutral(cls) -> ExpressionConfig:
        return cls()

NEUTRAL_EXPRESSION = ExpressionConfig.neutral()
