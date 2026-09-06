# slo-autoscaler

Does forecasting the workload actually help an autoscaler, or does it just move
the forecast error somewhere less visible?

Most student autoscaling projects stop at predicting CPU usage and reporting a
low error. That does not show whether the scaling policy avoids SLO violations
or uses fewer resources. This project runs the whole decision loop and compares
four policies on the two things that matter: how often the latency SLO is
broken, and how many replica-seconds it costs to get there.

## The four policies

| Policy | How it decides |
|--------|----------------|
| `static` | Fixed replica count. The do-nothing baseline. |
| `hpa` | Kubernetes-style reactive scaling on observed CPU vs a 60% target. |
| `predictive` | Sizes for the upper-quantile forecast of next-step demand (gradient-boosted quantile regression). |
| `oracle` | Same math as `predictive`, but the forecast is the exact next value. An upper bound, not a real option. |

Each policy runs against the same four workload shapes (steady, spike, ramp,
regime shift), the same five random seeds, and the same one-step actuation
delay. Decisions take effect one step after they are made, so a reactive policy
pays for being late.

## Offline results so far

Five-seed means. Lower is better on both columns.

| Scenario | Policy | SLO violation rate | Replica-steps |
|----------|--------|-------------------:|--------------:|
| spike | hpa | 0.008 | 178 |
| spike | predictive | 0.075 | 337 |
| spike | oracle | 0.000 | 222 |
| regime_shift | hpa | 0.000 | 416 |
| regime_shift | predictive | 0.000 | 375 |
| ramp | hpa | 0.000 | 451 |
| ramp | predictive | 0.000 | 463 |

On the spike workload the predictive policy loses to plain HPA: more replicas
and a higher violation rate. The quantile forecaster cannot see a step change
coming from lagged features, so it scales up after the fact and oscillates. The
oracle handles the same spike cleanly, which shows the ceiling is real but the
forecaster does not reach it.

On the regime shift the predictive policy uses about 10% fewer replica-steps
than HPA with no violations. That is a small, genuine win.

The `forecast_vs_slo.png` plot shows runs with a forecast MAE near 10 that have
zero violations, next to runs with MAE near 7 that violate 7.5% of the time.
Forecast accuracy and decision quality are not the same axis.

This is an offline simulation with an analytic latency curve. Live Kubernetes
measurements come next (see the plan). A result is only called an improvement
once the experiment output exists.

## Run it

Python 3.12. No Docker or Kubernetes needed for the offline study.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -e '.[dev,service]'
.venv/bin/python -m pytest -q
.venv/bin/python -m autoscaler_lab.cli run-offline \
    --config configs/experiment.json --output results/offline
```

This writes `results/offline/summary.json` (80 runs), one time series per run,
and two plots: `pareto.png` (cost vs violations) and `forecast_vs_slo.png`.

## Layout

```
src/autoscaler_lab/
  workload.py     deterministic scenarios
  metrics.py      analytic service curve, experiment summary
  policies.py     static / hpa / predictive decisions, all bounded to [1, 6]
  forecast.py     persistence, quantile, and oracle forecasters
  simulator.py    one-step-delayed closed loop
  experiment.py   the run matrix
  cli.py          run-offline entry point
configs/experiment.json   the fixed 4 x 4 x 5 matrix
```

## Method notes

- Seed 42 by default. Every result records its seed.
- Policies cannot request replicas outside `[1, 6]`; the simulator rejects it if they try.
- Only the oracle forecaster can see future demand. The others get history up to the current step and nothing more, and a test enforces this.
- No single blended score. Cost and violations are reported as a Pareto relationship so the reader picks the trade-off.

## Status

Offline study is complete and reproducible from one command. Live kind
experiments, a predictive controller for real Kubernetes, GitHub Actions, and a
full write-up are planned but not built yet.
