"""Repeatable offline experiment matrix: run every scenario x policy x seed,
serialize results, and draw two decision-focused plots. No blended score.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: works in CI
import matplotlib.pyplot as plt  # noqa: E402

from autoscaler_lab.forecast import (  # noqa: E402
    OracleForecaster,
    PersistenceForecaster,
    QuantileForecaster,
)
from autoscaler_lab.metrics import ExperimentSummary, ServiceModel, summarize  # noqa: E402
from autoscaler_lab.policies import HpaPolicy, PredictivePolicy, StaticPolicy  # noqa: E402
from autoscaler_lab.simulator import run_simulation  # noqa: E402
from autoscaler_lab.workload import generate_workload  # noqa: E402


def _build_policy(name: str, cfg: dict):
    if name == "static":
        return StaticPolicy(replicas=cfg["static_replicas"])
    if name == "hpa":
        return HpaPolicy(
            target_cpu=cfg["target_cpu"],
            min_replicas=cfg["min_replicas"],
            max_replicas=cfg["max_replicas"],
        )
    if name in ("predictive", "oracle"):
        return PredictivePolicy(
            capacity_per_replica=cfg["capacity_rps_per_replica"],
            target_utilization=cfg["target_cpu"] / 100.0,
            min_replicas=cfg["min_replicas"],
            max_replicas=cfg["max_replicas"],
        )
    raise ValueError(f"unknown policy: {name!r}")


def _build_forecaster(name: str, workload):
    if name == "predictive":
        return QuantileForecaster()
    if name == "oracle":
        return OracleForecaster(workload)
    return PersistenceForecaster(0.20)  # unused by static / hpa


def _atomic_write_json(path: Path, payload) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    os.replace(tmp, path)


def run_matrix(config_path: Path, output_dir: Path) -> list[ExperimentSummary]:
    cfg = json.loads(Path(config_path).read_text())
    output_dir = Path(output_dir)
    (output_dir / "timeseries").mkdir(parents=True, exist_ok=True)

    service = ServiceModel(
        capacity_rps_per_replica=cfg["capacity_rps_per_replica"],
        slo_ms=cfg["slo_ms"],
    )
    summaries: list[ExperimentSummary] = []

    for scenario in cfg["scenarios"]:
        for policy_name in cfg["policies"]:
            for seed in cfg["seeds"]:
                workload = generate_workload(scenario, cfg["steps"], seed)
                policy = _build_policy(policy_name, cfg)
                forecaster = _build_forecaster(policy_name, workload)

                states = run_simulation(
                    workload,
                    policy,
                    forecaster,
                    service,
                    refit_every=cfg["refit_every"],
                    initial_replicas=cfg["initial_replicas"],
                )
                summary = summarize(
                    states, policy_name, scenario, seed, slo_ms=cfg["slo_ms"]
                )
                summaries.append(summary)

                ts_path = output_dir / "timeseries" / f"{scenario}_{policy_name}_{seed}.json"
                _atomic_write_json(ts_path, [asdict(s) for s in states])

    _atomic_write_json(
        output_dir / "summary.json",
        {"config": cfg, "runs": [asdict(s) for s in summaries]},
    )
    _plot_pareto(summaries, output_dir / "pareto.png")
    _plot_forecast_vs_slo(summaries, output_dir / "forecast_vs_slo.png")
    return summaries


def _mean_std(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return mean, var**0.5


def _plot_pareto(summaries: list[ExperimentSummary], path: Path) -> None:
    by_policy: dict[str, list[ExperimentSummary]] = defaultdict(list)
    for row in summaries:
        by_policy[row.policy].append(row)

    fig, ax = plt.subplots(figsize=(7, 5))
    for policy, rows in by_policy.items():
        x_mean, x_std = _mean_std([r.replica_steps for r in rows])
        y_mean, y_std = _mean_std([r.slo_violation_rate for r in rows])
        ax.errorbar(
            x_mean, y_mean, xerr=x_std, yerr=y_std,
            fmt="o", capsize=4, label=policy, markersize=8,
        )
    ax.set_xlabel("replica-steps (resource cost)")
    ax.set_ylabel("SLO violation rate")
    ax.set_title("Cost vs SLO violations (mean +/- std over seeds, all scenarios)")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _plot_forecast_vs_slo(summaries: list[ExperimentSummary], path: Path) -> None:
    predictive = [
        r for r in summaries if r.policy == "predictive" and r.forecast_mae is not None
    ]
    fig, ax = plt.subplots(figsize=(7, 5))
    if predictive:
        ax.scatter(
            [r.forecast_mae for r in predictive],
            [r.slo_violation_rate for r in predictive],
            alpha=0.7,
        )
    ax.set_xlabel("forecast MAE (rps)")
    ax.set_ylabel("SLO violation rate")
    ax.set_title("Does lower forecast error mean fewer SLO violations? (predictive runs)")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
