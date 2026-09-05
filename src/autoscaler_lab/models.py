"""Immutable domain records shared across simulation, policies, and reporting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadPoint:
    step: int
    demand_rps: float
