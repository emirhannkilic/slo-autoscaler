"""Live predictive scaling controller for a real Kubernetes deployment.

The offline PredictivePolicy, but the CPU signal comes from ``kubectl top`` and
the decision is applied with ``kubectl scale``. It forecasts total pod CPU with
the same QuantileForecaster used offline, sizes for the upper quantile, and
clamps every decision to [min, max].

Never invokes a shell. Stops after three consecutive metric failures rather
than scaling on stale or empty data.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone

from autoscaler_lab.forecast import QuantileForecaster

_MAX_CONSECUTIVE_FAILURES = 3
_REFIT_EVERY = 6


def parse_cpu_millicores(text: str) -> list[int]:
    """Parse the CPU column of ``kubectl top pods`` output into millicores.

    Accepts ``<n>m`` (millicores) or a bare integer (whole cores -> * 1000).
    Rejects empty output and malformed rows instead of treating them as zero.
    """
    rows = [line.split() for line in text.strip().splitlines() if line.strip()]
    if not rows:
        raise ValueError("no cpu metrics: kubectl top returned nothing")

    values: list[int] = []
    for row in rows:
        if len(row) < 2:
            raise ValueError(f"malformed kubectl top row: {row!r}")
        token = row[1]
        try:
            if token.endswith("m"):
                values.append(int(token[:-1]))
            else:
                values.append(int(token) * 1000)  # whole cores -> millicores
        except ValueError as exc:
            raise ValueError(f"cannot parse cpu token {token!r}") from exc
    return values


def build_scale_command(namespace: str, deployment: str, replicas: int) -> list[str]:
    return [
        "kubectl", "scale", f"deployment/{deployment}",
        "--namespace", namespace, "--replicas", str(replicas),
    ]


def decide_replicas(
    upper_millicores: float,
    per_replica_millicores: float,
    min_replicas: int,
    max_replicas: int,
) -> int:
    """Size for the upper-quantile CPU forecast, then clamp."""
    desired = math.ceil(upper_millicores / per_replica_millicores)
    return max(min_replicas, min(max_replicas, desired))


class _Loop:
    """One controller step, separated so the decision path is testable
    without kubectl or real time."""

    def __init__(self, per_replica_millicores, min_replicas, max_replicas, refit_every=_REFIT_EVERY):
        self.forecaster = QuantileForecaster()
        self.history: list[float] = []
        self.tick = 0
        self.per_replica = per_replica_millicores
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.refit_every = refit_every

    def step(self, cpu_total: float, active_replicas: int) -> dict:
        self.tick += 1
        self.history.append(float(cpu_total))
        if len(self.history) >= 30 and self.tick % self.refit_every == 0:
            self.forecaster.fit(self.history)
        forecast = self.forecaster.predict(self.history, len(self.history))
        requested = decide_replicas(
            forecast.upper, self.per_replica, self.min_replicas, self.max_replicas
        )
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tick": self.tick,
            "history_size": len(self.history),
            "cpu_total_millicores": cpu_total,
            "active_replicas": active_replicas,
            "forecast_point": forecast.point,
            "forecast_upper": forecast.upper,
            "requested_replicas": requested,
            "fallback_used": self.forecaster.last_was_fallback,
        }


def _run(cmd: list[str]) -> str:
    return subprocess.run(
        cmd, check=True, capture_output=True, text=True
    ).stdout


def _current_replicas(namespace: str, deployment: str) -> int:
    out = _run([
        "kubectl", "get", "deployment", deployment, "--namespace", namespace,
        "-o", "jsonpath={.status.replicas}",
    ])
    return int(out) if out.strip() else 0


def _sample_cpu_total(namespace: str, selector: str) -> int:
    out = _run([
        "kubectl", "top", "pods", "--selector", selector,
        "--namespace", namespace, "--no-headers",
    ])
    return sum(parse_cpu_millicores(out))


def run_controller(
    namespace: str,
    deployment: str,
    selector: str,
    interval: int,
    output: str,
    per_replica_millicores: float,
    min_replicas: int,
    max_replicas: int,
) -> None:
    loop = _Loop(per_replica_millicores, min_replicas, max_replicas)
    consecutive_failures = 0

    with open(output, "w") as log:
        while True:
            try:
                cpu_total = _sample_cpu_total(namespace, selector)
                active = _current_replicas(namespace, deployment)
                consecutive_failures = 0
            except (subprocess.CalledProcessError, ValueError) as exc:
                consecutive_failures += 1
                print(f"metric failure {consecutive_failures}: {exc}", file=sys.stderr)
                if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                    raise SystemExit(
                        f"stopping: {_MAX_CONSECUTIVE_FAILURES} consecutive metric failures"
                    )
                time.sleep(interval)
                continue

            record = loop.step(cpu_total, active)
            log.write(json.dumps(record) + "\n")
            log.flush()

            if record["requested_replicas"] != active:
                _run(build_scale_command(namespace, deployment, record["requested_replicas"]))

            time.sleep(interval)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="autoscaler_lab.controller")
    parser.add_argument("--namespace", default="default")
    parser.add_argument("--deployment", default="load-target")
    parser.add_argument("--selector", default="app=load-target")
    parser.add_argument("--interval", type=int, default=15)
    parser.add_argument("--output", required=True)
    parser.add_argument("--per-replica-millicores", type=float, default=60.0)
    parser.add_argument("--min-replicas", type=int, default=1)
    parser.add_argument("--max-replicas", type=int, default=6)
    args = parser.parse_args(argv)

    run_controller(
        namespace=args.namespace,
        deployment=args.deployment,
        selector=args.selector,
        interval=args.interval,
        output=args.output,
        per_replica_millicores=args.per_replica_millicores,
        min_replicas=args.min_replicas,
        max_replicas=args.max_replicas,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
