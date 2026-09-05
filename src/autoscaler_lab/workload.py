"""Deterministic workload scenarios. No scaling logic lives here."""

from __future__ import annotations

import numpy as np

from autoscaler_lab.models import WorkloadPoint

_KINDS = ("steady", "spike", "ramp", "regime_shift")


def generate_workload(kind: str, steps: int, seed: int) -> list[WorkloadPoint]:
    """Return a reproducible demand trace for the given scenario.

    Uses an isolated RNG (``default_rng``) so the trace depends only on
    ``kind``, ``steps``, and ``seed`` -- never on global numpy state.
    """
    if kind not in _KINDS:
        raise ValueError(f"unknown workload: {kind!r}; expected one of {_KINDS}")
    if steps <= 0:
        raise ValueError(f"steps must be positive, got {steps}")

    rng = np.random.default_rng(seed)

    if kind == "steady":
        demand = 20 + rng.normal(0, 1.5, steps)
    elif kind == "spike":
        demand = np.full(steps, 15.0)
        demand[steps // 3 : steps // 3 + 10] = 90.0
    elif kind == "ramp":
        demand = np.linspace(10, 100, steps)
    else:  # regime_shift
        demand = np.concatenate(
            (np.full(steps // 2, 18.0), np.full(steps - steps // 2, 65.0))
        )

    demand = demand + rng.normal(0, 1.0, steps)
    demand = np.maximum(demand, 0.0)

    return [WorkloadPoint(step=i, demand_rps=float(demand[i])) for i in range(steps)]
