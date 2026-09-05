"""Replica decisions. No experiment orchestration, no workload history reads.

Each policy takes the current observed state and (optionally) a forecast, and
returns a bounded ScalingDecision for the next step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from autoscaler_lab.models import Forecast, ScalingDecision, SystemState


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@dataclass(frozen=True)
class StaticPolicy:
    """Fixed replica count -- the do-nothing baseline."""

    replicas: int

    def decide(self, current: SystemState, forecast: Forecast | None) -> ScalingDecision:
        return ScalingDecision(self.replicas, f"static at {self.replicas}")


@dataclass(frozen=True)
class HpaPolicy:
    """Kubernetes-style reactive HPA: scale on observed CPU vs a target."""

    target_cpu: float
    min_replicas: int
    max_replicas: int
    tolerance: float = 0.10

    def decide(self, current: SystemState, forecast: Forecast | None) -> ScalingDecision:
        ratio = current.cpu_utilization / self.target_cpu
        if abs(1.0 - ratio) <= self.tolerance:
            desired = current.replicas
        else:
            desired = math.ceil(current.replicas * ratio)
        desired = _clamp(desired, self.min_replicas, self.max_replicas)
        reason = (
            f"hpa cpu={current.cpu_utilization:.0f}% target={self.target_cpu:.0f}% "
            f"ratio={ratio:.2f}"
        )
        return ScalingDecision(desired, reason)


@dataclass(frozen=True)
class PredictivePolicy:
    """Forecast-driven: size for the upper-quantile demand of the next step."""

    capacity_per_replica: float
    target_utilization: float
    min_replicas: int
    max_replicas: int

    def decide(self, current: SystemState, forecast: Forecast | None) -> ScalingDecision:
        if forecast is None:
            raise ValueError("predictive policy requires a forecast")
        effective_capacity = self.capacity_per_replica * self.target_utilization
        desired = math.ceil(forecast.upper / effective_capacity)
        desired = _clamp(desired, self.min_replicas, self.max_replicas)
        reason = (
            f"predictive upper={forecast.upper:.1f}rps "
            f"eff_capacity={effective_capacity:.1f}rps/replica"
        )
        return ScalingDecision(desired, reason)
