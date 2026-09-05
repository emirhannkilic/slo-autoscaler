"""Analytic service response curve and experiment summary calculations.

No blended score: the study reports SLO violations and replica cost as a
Pareto relationship, not a single weighted number.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from autoscaler_lab.models import SystemState


@dataclass(frozen=True)
class ServiceModel:
    """Declared analytic model of how one service responds to load.

    These are simulation parameters, not measured production facts. The real
    latency numbers come from the live kind experiments.
    """

    capacity_rps_per_replica: float = 25.0
    base_latency_ms: float = 30.0
    slo_ms: float = 200.0

    def observe(self, demand_rps: float, replicas: int) -> tuple[float, float]:
        """Return (cpu_percent, p95_latency_ms) for this demand and replica count.

        Latency is flat until utilization passes 0.70, then grows quadratically
        with the overload -- a coarse stand-in for queueing blow-up near
        saturation.
        """
        if replicas < 1:
            raise ValueError(f"replicas must be >= 1, got {replicas}")
        if demand_rps < 0:
            raise ValueError(f"demand_rps must be >= 0, got {demand_rps}")

        load_per_replica = demand_rps / replicas
        utilization_ratio = load_per_replica / self.capacity_rps_per_replica
        cpu_percent = min(200.0, utilization_ratio * 100.0)
        overload = max(0.0, utilization_ratio - 0.70)
        p95_latency_ms = self.base_latency_ms * (1.0 + 12.0 * overload**2)
        return cpu_percent, p95_latency_ms


@dataclass(frozen=True)
class ExperimentSummary:
    scenario: str
    policy: str
    seed: int
    slo_violation_rate: float
    replica_steps: int
    mean_replicas: float
    mean_p95_latency_ms: float
    max_p95_latency_ms: float
    scaling_events: int
    oscillations: int
    forecast_mae: float | None
    fallback_count: int


def _count_oscillations(replicas: Sequence[int]) -> int:
    """Sign changes between consecutive non-zero replica deltas."""
    deltas = [b - a for a, b in zip(replicas, replicas[1:]) if b != a]
    return sum(1 for x, y in zip(deltas, deltas[1:]) if (x > 0) != (y > 0))


def summarize(
    states: Sequence[SystemState],
    policy: str,
    scenario: str,
    seed: int,
    slo_ms: float = 200.0,
) -> ExperimentSummary:
    if not states:
        raise ValueError("cannot summarize an empty state sequence")

    replicas = [s.replicas for s in states]
    latencies = [s.p95_latency_ms for s in states]
    violations = sum(1 for lat in latencies if lat > slo_ms)

    # forecast_rps at step t predicts demand at step t+1, so align with the
    # *following* state's demand, not the current one.
    errors = [
        abs(current.forecast_rps - following.demand_rps)
        for current, following in zip(states, states[1:])
        if current.forecast_rps is not None
    ]
    forecast_mae = sum(errors) / len(errors) if errors else None

    return ExperimentSummary(
        scenario=scenario,
        policy=policy,
        seed=seed,
        slo_violation_rate=violations / len(states),
        replica_steps=sum(replicas),
        mean_replicas=sum(replicas) / len(replicas),
        mean_p95_latency_ms=sum(latencies) / len(latencies),
        max_p95_latency_ms=max(latencies),
        scaling_events=sum(1 for a, b in zip(replicas, replicas[1:]) if a != b),
        oscillations=_count_oscillations(replicas),
        forecast_mae=forecast_mae,
        fallback_count=sum(1 for s in states if s.fallback_used),
    )
