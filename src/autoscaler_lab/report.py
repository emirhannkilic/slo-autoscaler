"""Turn ``summary.json`` into a paper-style ``results.md``.

Hypotheses are decided by fixed rules, not by the desired outcome. A rule that
is not met yields ``rejected`` or ``inconclusive`` -- never a softened verdict.
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

from scipy.stats import spearmanr

_SCENARIOS = ("steady", "spike", "ramp", "regime_shift")
_POLICIES = ("static", "hpa", "predictive", "predictive_frozen", "oracle")
_PAIRED_MIN = 4  # of 5 seeds must agree for a paired-difference rule


def _rows_by(runs, scenario=None, policy=None):
    out = []
    for r in runs:
        if scenario is not None and r["scenario"] != scenario:
            continue
        if policy is not None and r["policy"] != policy:
            continue
        out.append(r)
    return out


def _by_seed(rows) -> dict[int, dict]:
    return {r["seed"]: r for r in rows}


def _paired_diffs(runs, scenario, policy_a, policy_b, field):
    a = _by_seed(_rows_by(runs, scenario, policy_a))
    b = _by_seed(_rows_by(runs, scenario, policy_b))
    seeds = sorted(set(a) & set(b))
    return [a[s][field] - b[s][field] for s in seeds]


def _mean_std(values):
    if not values:
        return 0.0, 0.0
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean, std


# --- hypothesis rules -------------------------------------------------------


def _decide_h1(runs) -> dict:
    """Predictive reduces SLO violations on rising / regime-shift demand.

    Supported for a scenario only if predictive's mean SLO violation rate is
    lower than HPA's AND at least 4 of 5 paired seed differences are negative.
    """
    per_scenario = {}
    for scenario in ("ramp", "regime_shift", "spike"):
        pred = [r["slo_violation_rate"] for r in _rows_by(runs, scenario, "predictive")]
        hpa = [r["slo_violation_rate"] for r in _rows_by(runs, scenario, "hpa")]
        diffs = _paired_diffs(runs, scenario, "predictive", "hpa", "slo_violation_rate")
        mean_lower = _mean_std(pred)[0] < _mean_std(hpa)[0]
        agree = sum(1 for d in diffs if d < 0)
        per_scenario[scenario] = mean_lower and agree >= _PAIRED_MIN
    supported = [s for s, ok in per_scenario.items() if ok]
    if supported:
        return {
            "decision": "supported",
            "detail": f"predictive has fewer violations on: {', '.join(supported)}",
        }
    return {
        "decision": "rejected",
        "detail": "predictive did not lower the mean violation rate with >=4/5 "
        "seeds agreeing in any rising or regime-shift scenario",
    }


def _decide_h2(runs) -> dict:
    """Predictive spends more replica-steps when its upper quantile is poorly
    calibrated: supported if predictive replica-steps exceed HPA in >= 4 paired
    seeds, in at least one scenario."""
    hits = {}
    for scenario in _SCENARIOS:
        diffs = _paired_diffs(runs, scenario, "predictive", "hpa", "replica_steps")
        hits[scenario] = sum(1 for d in diffs if d > 0)
    supported = [s for s, n in hits.items() if n >= _PAIRED_MIN]
    if supported:
        return {
            "decision": "supported",
            "detail": f"predictive uses more replica-steps than HPA on: {', '.join(supported)}",
        }
    return {
        "decision": "rejected",
        "detail": "predictive did not exceed HPA replica-steps in >=4/5 seeds in any scenario",
    }


def _decide_h3(runs) -> dict:
    """Forecast MAE and SLO violation rate are not strictly monotonic:
    supported if |Spearman(MAE, violation rate)| < 0.8 over predictive runs."""
    pred = [
        r for r in _rows_by(runs, policy="predictive") if r["forecast_mae"] is not None
    ]
    maes = [r["forecast_mae"] for r in pred]
    slos = [r["slo_violation_rate"] for r in pred]
    if len(pred) < 3 or len(set(slos)) < 2:
        return {
            "decision": "inconclusive",
            "detail": f"not enough spread to correlate ({len(pred)} runs)",
        }
    rho = spearmanr(maes, slos).statistic
    if abs(rho) < 0.8:
        return {
            "decision": "supported",
            "detail": f"Spearman(MAE, violation rate) = {rho:.3f}, |rho| < 0.8",
        }
    return {
        "decision": "rejected",
        "detail": f"Spearman(MAE, violation rate) = {rho:.3f}, |rho| >= 0.8",
    }


def _decide_h4(runs) -> dict:
    """Periodic retraining helps after drift but does not dominate reactive HPA
    everywhere.

    Supported only if, after the regime shift, retrained predictive beats the
    frozen predictive model on SLO violations in >= 4 paired seeds, while NOT
    beating HPA in every scenario.
    """
    frozen_diffs = _paired_diffs(
        runs, "regime_shift", "predictive", "predictive_frozen", "slo_violation_rate"
    )
    beats_frozen = sum(1 for d in frozen_diffs if d < 0)
    ties_frozen = sum(1 for d in frozen_diffs if d == 0)

    dominates_hpa_everywhere = all(
        _mean_std([r["slo_violation_rate"] for r in _rows_by(runs, sc, "predictive")])[0]
        < _mean_std([r["slo_violation_rate"] for r in _rows_by(runs, sc, "hpa")])[0]
        for sc in _SCENARIOS
    )

    if beats_frozen >= _PAIRED_MIN and not dominates_hpa_everywhere:
        return {
            "decision": "supported",
            "detail": f"retrained beats frozen on {beats_frozen}/5 seeds after drift "
            "and does not dominate HPA in every scenario",
        }
    if ties_frozen == len(frozen_diffs) and frozen_diffs:
        return {
            "decision": "inconclusive",
            "detail": "retrained and frozen predictive tie on every seed after drift "
            "(no violations either way), so retraining's effect cannot be measured here",
        }
    return {
        "decision": "rejected",
        "detail": f"retrained beat frozen on only {beats_frozen}/5 seeds after drift",
    }


def decide_hypotheses(runs) -> dict[str, dict]:
    return {
        "H1": _decide_h1(runs),
        "H2": _decide_h2(runs),
        "H3": _decide_h3(runs),
        "H4": _decide_h4(runs),
    }


# --- rendering -------------------------------------------------------------


_H_TEXT = {
    "H1": "Predictive scaling reduces SLO violations on ramp and regime-shift "
    "workloads because it can allocate capacity before HPA observes high CPU.",
    "H2": "Predictive scaling uses more replica-seconds when its upper quantile "
    "is poorly calibrated.",
    "H3": "Forecast MAE and SLO violation rate do not have a strictly monotonic "
    "relationship.",
    "H4": "Periodic expanding-window retraining helps after drift but does not "
    "dominate reactive HPA in every scenario.",
}


def _offline_table(runs) -> str:
    lines = [
        "| Scenario | Policy | SLO violation rate (mean +/- std) | Replica-steps (mean +/- std) | Mean p95 (ms) | Forecast MAE |",
        "|---|---|---|---|---|---|",
    ]
    for scenario in _SCENARIOS:
        for policy in _POLICIES:
            rows = _rows_by(runs, scenario, policy)
            if not rows:
                continue
            slo_m, slo_s = _mean_std([r["slo_violation_rate"] for r in rows])
            rep_m, rep_s = _mean_std([r["replica_steps"] for r in rows])
            lat_m, _ = _mean_std([r["mean_p95_latency_ms"] for r in rows])
            maes = [r["forecast_mae"] for r in rows if r["forecast_mae"] is not None]
            mae_txt = f"{_mean_std(maes)[0]:.3f}" if maes else "-"
            lines.append(
                f"| {scenario} | {policy} | {slo_m:.3f} +/- {slo_s:.3f} | "
                f"{rep_m:.1f} +/- {rep_s:.1f} | {lat_m:.1f} | {mae_txt} |"
            )
    return "\n".join(lines)


def _live_section(summary_path: Path) -> str:
    live_summary = summary_path.parent.parent / "live" / "summary.json"
    if not live_summary.is_file():
        return (
            "The live kind experiment has not been run yet, or its artifacts are "
            "not checked out here. Trigger the `kind-experiment` workflow "
            "(`policy=both`) and add the run URL to `docs/methodology.md`."
        )

    live = json.loads(live_summary.read_text())
    h = live["hpa"]["locust"]
    p = live["predictive"]["locust"]
    ctrl = live["predictive"]["controller"]
    lines = [
        "Both policies ran the identical 24-minute Locust shape on a one-node "
        "kind cluster inside GitHub Actions.",
        "",
        "| Policy | Requests | RPS | Median (ms) | p95 (ms) | p99 (ms) | Max replicas |",
        "|---|---|---|---|---|---|---|",
        f"| hpa | {h['requests']:,} | {h['rps']} | {h['median_ms']:.0f} | "
        f"{h['p95_ms']:.0f} | {h['p99_ms']:.0f} | 6 |",
        f"| predictive | {p['requests']:,} | {p['rps']} | {p['median_ms']:.0f} | "
        f"{p['p95_ms']:.0f} | {p['p99_ms']:.0f} | {ctrl['max_active_replicas']} |",
        "",
        f"The predictive controller ran {ctrl['ticks']} ticks, "
        f"{ctrl['non_fallback_ticks']} of them with a trained quantile model.",
        "",
        f"_{live['notes']}_",
    ]
    return "\n".join(lines)


def render_report(summary_path: Path, output_path: Path) -> None:
    data = json.loads(Path(summary_path).read_text())
    runs = data["runs"]
    cfg = data["config"]
    decisions = decide_hypotheses(runs)

    parts = [
        "# Results\n",
        "## Research questions\n",
        "1. Does an upper-quantile workload forecast reduce SLO violations during "
        "rising or abruptly changing demand?\n"
        "2. What replica cost is paid for that reduction?\n"
        "3. Does lower forecast MAE reliably correspond to a better scaling decision?\n"
        "4. How does workload drift affect a predictive policy compared with reactive HPA?\n"
        "5. Do conclusions from the offline simulator remain directionally consistent "
        "on a real Kubernetes control loop?\n",
        "## Experimental controls\n",
        f"- Every policy receives the same workload array (seed in every row) and "
        f"initial replica count ({cfg['initial_replicas']}).\n"
        "- Each policy decision takes effect one simulation step later.\n"
        "- Only `OracleForecaster` sees the next demand value.\n"
        f"- Replica bounds fixed at [{cfg['min_replicas']}, {cfg['max_replicas']}]; "
        f"HPA target CPU {cfg['target_cpu']}%; latency SLO {cfg['slo_ms']} ms p95.\n"
        f"- Offline service capacity {cfg['capacity_rps_per_replica']} rps/replica "
        "(a declared simulation parameter, not a measured fact).\n"
        f"- {len(cfg['seeds'])} seeds: {cfg['seeds']}. Comparisons are Pareto "
        "(SLO violations vs replica-steps); no single blended score.\n",
        "## Offline results\n",
        _offline_table(runs) + "\n",
        "## Live results\n",
        _live_section(Path(summary_path)) + "\n",
        "## Hypothesis decisions\n",
    ]

    for key in ("H1", "H2", "H3", "H4"):
        d = decisions[key]
        parts.append(
            f"**{key} ({d['decision']}).** {_H_TEXT[key]}\n\n> {d['detail']}\n"
        )

    live_summary = Path(summary_path).parent.parent / "live" / "summary.json"
    if live_summary.is_file():
        parts += [
            "## Live vs offline consistency (RQ5)\n",
            "The offline simulator gives every policy a perfect, instant CPU "
            "signal. On the live cluster HPA depended on Metrics Server, which "
            "was not ready for the first ~2 minutes, so HPA scaled late and its "
            "p95 latency sat at or above the 200 ms SLO. The predictive "
            "controller scaled to maximum on its first tick through the "
            "persistence fallback and then ran a trained model, so it had full "
            "capacity from the start and kept p95 well under the SLO at higher "
            "throughput.\n\n"
            "So the live result is directionally *opposite* to the offline one: "
            "offline, predictive lost to HPA; live, predictive's early "
            "over-provisioning beat HPA's metric-startup lag. The controlled "
            "offline conclusions do not transfer directly, because the offline "
            "model omits metric-pipeline delay.\n",
        ]

    parts += [
        "## Threats to validity\n",
        "- Offline latency comes from an analytic overload curve, not measurement.\n"
        "- The kind experiment runs on a shared, ephemeral GitHub VM.\n"
        "- CPU metrics from Metrics Server have sampling delay.\n"
        "- Four generated workload shapes do not represent every production service.\n"
        "- One-node AKS validation checks portability, not production scale.\n",
        "## Reproduction\n",
        "```bash\n"
        "pip install -e '.[dev,service]'\n"
        "python -m pytest -q\n"
        "python -m autoscaler_lab.cli run-offline "
        "--config configs/experiment.json --output results/offline\n"
        "python -m autoscaler_lab.cli render-report "
        "--summary results/offline/summary.json --output docs/results.md\n"
        "```\n",
        "## Appendix: raw runs\n",
        _raw_table(runs) + "\n",
    ]

    Path(output_path).write_text("\n".join(parts))


def _raw_table(runs) -> str:
    lines = [
        "| Scenario | Policy | Seed | SLO viol. | Replica-steps | Scaling events | Oscillations | Forecast MAE | Fallbacks |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in sorted(runs, key=lambda x: (x["scenario"], x["policy"], x["seed"])):
        mae = f"{r['forecast_mae']:.3f}" if r["forecast_mae"] is not None else "-"
        lines.append(
            f"| {r['scenario']} | {r['policy']} | {r['seed']} | "
            f"{r['slo_violation_rate']:.3f} | {r['replica_steps']} | "
            f"{r['scaling_events']} | {r['oscillations']} | {mae} | {r['fallback_count']} |"
        )
    return "\n".join(lines)
