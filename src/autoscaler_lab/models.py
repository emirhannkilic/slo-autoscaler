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


@dataclass(frozen=True)
class Forecast:
    """A demand forecast for the next step: median point and upper quantile.

    Invariant ``upper >= point >= 0`` is enforced by the forecasters (Task 4),
    not here, so this stays a plain value record.
    """

    point: float
    upper: float


@dataclass(frozen=True)
class ScalingDecision:
    replicas: int
    reason: str
