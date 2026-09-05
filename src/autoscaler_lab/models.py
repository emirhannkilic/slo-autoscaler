"""Immutable domain records shared across simulation, policies, and reporting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadPoint:
    step: int
    demand_rps: float


@dataclass(frozen=True)
class SystemState:
    """One observed simulation step: what happened, plus the forecast that fed it."""

    step: int
    demand_rps: float
    replicas: int
    cpu_utilization: float
    p95_latency_ms: float
    forecast_rps: float | None
    forecast_upper_rps: float | None
    fallback_used: bool
    decision_replicas: int = 0  # replicas requested for the next step (actuation delay)


@dataclass(frozen=True)
class Forecast:
    """A demand forecast for the next step: median point and upper quantile.

    Enforces ``upper >= point >= 0``. Use ``Forecast.make`` to build one from
    two possibly-crossed quantile estimates.
    """

    point: float
    upper: float

    def __post_init__(self) -> None:
        if self.point < 0 or self.upper < self.point:
            raise ValueError(
                f"invalid forecast: need upper >= point >= 0, got "
                f"point={self.point}, upper={self.upper}"
            )

    @classmethod
    def make(cls, point: float, upper: float) -> "Forecast":
        """Clamp point to >= 0 and lift a crossed upper back above point."""
        point = max(0.0, float(point))
        upper = max(point, float(upper))
        return cls(point=point, upper=upper)


@dataclass(frozen=True)
class ScalingDecision:
    replicas: int
    reason: str
