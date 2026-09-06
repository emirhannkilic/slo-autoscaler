# Methodology

## Design

Four scaling policies (`static`, `hpa`, `predictive`, `oracle`) plus
`predictive_frozen` for the drift comparison, run against four workload
families (`steady`, `spike`, `ramp`, `regime_shift`) on five seeds (42 to 46),
120 steps each. That is a fixed 4 x 5 x 5 = 100-run matrix in
`configs/experiment.json`.

Every policy gets the same workload array and the same initial replica count.
A decision made at step `t` takes effect at `t + 1`, so a reactive policy pays
for being late. Only `OracleForecaster` sees the next demand value; a test
enforces that a normal forecaster only ever receives history up to the current
step.

## Metrics

Reported per run: SLO violation rate, replica-steps (the resource-cost proxy),
mean and max p95 latency, scaling events, oscillations, forecast MAE where a
forecast is used, and fallback count. There is no single blended score. Cost
and violations are compared as a Pareto relationship so the reader chooses the
trade-off.

Offline latency comes from a declared analytic curve, not measurement:
utilization is flat until 0.70 of capacity, then p95 grows as
`base * (1 + 12 * overload**2)`. Capacity is 25 rps per replica. These are
simulation parameters.

## Hypothesis rules

Decided by fixed rules in `report.py`, not by the desired outcome. A rule that
is not met yields `rejected` or `inconclusive`, never a softened verdict.

- **H1** supported for a scenario only if predictive has a lower mean SLO
  violation rate than HPA and at least 4 of 5 paired seed differences are
  negative.
- **H2** supported if predictive replica-steps exceed HPA in at least 4 paired
  seeds in at least one scenario.
- **H3** supported if the Spearman correlation between predictive forecast MAE
  and SLO violation rate is below 0.8 in absolute value.
- **H4** supported only if retrained predictive beats frozen predictive on SLO
  violations in at least 4 paired seeds after the regime shift, while not
  dominating HPA in every scenario. If retrained and frozen tie on every seed,
  the verdict is inconclusive.

## Reproducibility evidence

### Offline study

One command from a clean Python 3.12 environment:

```bash
pip install -e '.[dev,service]'
python -m pytest -q
python -m autoscaler_lab.cli run-offline --config configs/experiment.json --output results/offline
python -m autoscaler_lab.cli render-report --summary results/offline/summary.json --output docs/results.md
```

### Live kind experiment

Triggered manually from the Actions tab (`kind-experiment` workflow,
`policy=both`). Each run builds the service image, creates an ephemeral kind
cluster, installs Metrics Server v0.7.2, runs the 24-minute Locust workload,
polls replica count and CPU, and uploads results plus diagnostics regardless
of outcome.

Successful runs:

- HPA: _(add the Actions run URL here after the first green run)_
- Predictive: _(add the Actions run URL here after the first green run)_

A status badge is added only after the workflow has passed once.
