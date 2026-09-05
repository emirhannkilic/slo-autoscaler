"""One-step-delayed closed-loop autoscaling simulator. No plotting here.

Loop order per step ``t`` (order matters -- it keeps forecasts causal):
  1. apply the decision made at t-1
  2. observe CPU and latency for the current demand and active replicas
  3. append the current demand to history
  4. refit the forecaster on the schedule
  5. predict demand for t+1 from history
  6. request the replica count for t+1
  7. record the state and the next decision
"""

from __future__ import annotations

from collections.abc import Sequence

from autoscaler_lab.metrics import ServiceModel
from autoscaler_lab.models import SystemState, WorkloadPoint

_MIN_REPLICAS = 1
_MAX_REPLICAS = 6
_REFIT_MIN_HISTORY = 30


def run_simulation(
    workload: Sequence[WorkloadPoint],
    policy,
    forecaster,
    service_model: ServiceModel,
    refit_every: int = 12,
    initial_replicas: int = 1,
) -> list[SystemState]:
    if not workload:
        raise ValueError("workload must be non-empty")
    if not (_MIN_REPLICAS <= initial_replicas <= _MAX_REPLICAS):
        raise ValueError(
            f"initial_replicas must be in [{_MIN_REPLICAS}, {_MAX_REPLICAS}], "
            f"got {initial_replicas}"
        )
    if [p.step for p in workload] != list(range(len(workload))):
        raise ValueError("workload steps must be consecutive starting at 0")

    uses_forecast = getattr(policy, "needs_forecast", False)
    n = len(workload)
    history: list[float] = []
    states: list[SystemState] = []
    active_replicas = initial_replicas
    next_decision = initial_replicas

    for t in range(n):
        active_replicas = next_decision  # 1. apply t-1 decision
        demand = workload[t].demand_rps

        cpu, latency = service_model.observe(demand, active_replicas)  # 2. observe
        history.append(demand)  # 3. history

        forecast = None
        fallback_used = False
        if uses_forecast:
            if (
                t >= _REFIT_MIN_HISTORY and refit_every > 0 and t % refit_every == 0
            ):  # 4. refit
                forecaster.fit(history)
            # 5. predict. Called every step so a normal forecaster always sees
            # history of length 1..n. Oracle indexes the workload, so on the last
            # step it looks at t (clamped) -- the forecast is discarded there.
            target = t + 1 if t + 1 < n else t
            forecast = forecaster.predict(history, target)
            fallback_used = getattr(forecaster, "last_was_fallback", False)

        if t + 1 < n:
            current = SystemState(
                step=t,
                demand_rps=demand,
                replicas=active_replicas,
                cpu_utilization=cpu,
                p95_latency_ms=latency,
                forecast_rps=forecast.point if forecast else None,
                forecast_upper_rps=forecast.upper if forecast else None,
                fallback_used=fallback_used,
            )
            decision = policy.decide(current, forecast)  # 6. request
            if not (_MIN_REPLICAS <= decision.replicas <= _MAX_REPLICAS):
                raise ValueError(
                    f"policy requested {decision.replicas} replicas at step {t}, "
                    f"outside [{_MIN_REPLICAS}, {_MAX_REPLICAS}]"
                )
            next_decision = decision.replicas
            forecast_rps = forecast.point if forecast else None
            forecast_upper = forecast.upper if forecast else None
        else:
            # final step: no next workload point, so the decision is a no-op
            next_decision = active_replicas
            fallback_used = False
            forecast_rps = None
            forecast_upper = None

        states.append(
            SystemState(
                step=t,
                demand_rps=demand,
                replicas=active_replicas,
                cpu_utilization=cpu,
                p95_latency_ms=latency,
                forecast_rps=forecast_rps,
                forecast_upper_rps=forecast_upper,
                fallback_used=fallback_used,
                decision_replicas=next_decision,
            )
        )

    return states
