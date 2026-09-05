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
