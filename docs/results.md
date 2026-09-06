# Results

## Research questions

1. Does an upper-quantile workload forecast reduce SLO violations during rising or abruptly changing demand?
2. What replica cost is paid for that reduction?
3. Does lower forecast MAE reliably correspond to a better scaling decision?
4. How does workload drift affect a predictive policy compared with reactive HPA?
5. Do conclusions from the offline simulator remain directionally consistent on a real Kubernetes control loop?

## Experimental controls

- Every policy receives the same workload array (seed in every row) and initial replica count (1).
- Each policy decision takes effect one simulation step later.
- Only `OracleForecaster` sees the next demand value.
- Replica bounds fixed at [1, 6]; HPA target CPU 60%; latency SLO 200 ms p95.
- Offline service capacity 25 rps/replica (a declared simulation parameter, not a measured fact).
- 5 seeds: [42, 43, 44, 45, 46]. Comparisons are Pareto (SLO violations vs replica-steps); no single blended score.

## Offline results

| Scenario | Policy | SLO violation rate (mean +/- std) | Replica-steps (mean +/- std) | Mean p95 (ms) | Forecast MAE |
|---|---|---|---|---|---|
| steady | static | 0.000 +/- 0.000 | 358.0 +/- 0.0 | 30.0 | - |
| steady | hpa | 0.000 +/- 0.000 | 238.6 +/- 0.5 | 30.1 | - |
| steady | predictive | 0.000 +/- 0.000 | 239.0 +/- 0.0 | 30.0 | 1.588 |
| steady | predictive_frozen | 0.000 +/- 0.000 | 239.0 +/- 0.0 | 30.0 | 1.562 |
| steady | oracle | 0.000 +/- 0.000 | 238.6 +/- 0.5 | 30.0 | 0.000 |
| spike | static | 0.000 +/- 0.000 | 358.0 +/- 0.0 | 37.6 | - |
| spike | hpa | 0.008 +/- 0.000 | 177.6 +/- 4.3 | 46.8 | - |
| spike | predictive | 0.075 +/- 0.000 | 336.6 +/- 10.2 | 62.9 | 7.427 |
| spike | predictive_frozen | 0.083 +/- 0.000 | 239.0 +/- 0.0 | 66.5 | 7.121 |
| spike | oracle | 0.000 +/- 0.000 | 221.6 +/- 4.1 | 30.0 | 0.000 |
| ramp | static | 0.000 +/- 0.000 | 358.0 +/- 0.0 | 55.6 | - |
| ramp | hpa | 0.000 +/- 0.000 | 450.6 +/- 1.6 | 30.0 | - |
| ramp | predictive | 0.000 +/- 0.000 | 462.4 +/- 1.0 | 30.0 | 10.565 |
| ramp | predictive_frozen | 0.000 +/- 0.000 | 333.4 +/- 1.0 | 55.6 | 31.200 |
| ramp | oracle | 0.000 +/- 0.000 | 485.2 +/- 1.2 | 30.0 | 0.000 |
| regime_shift | static | 0.000 +/- 0.000 | 358.0 +/- 0.0 | 35.0 | - |
| regime_shift | hpa | 0.000 +/- 0.000 | 416.0 +/- 0.0 | 31.1 | - |
| regime_shift | predictive | 0.000 +/- 0.000 | 374.6 +/- 10.8 | 46.0 | 7.029 |
| regime_shift | predictive_frozen | 0.000 +/- 0.000 | 239.0 +/- 0.0 | 94.5 | 24.106 |
| regime_shift | oracle | 0.000 +/- 0.000 | 419.0 +/- 0.0 | 30.0 | 0.000 |

## Live results

The live kind experiment has not been run yet, or its artifacts are not checked out here. Trigger the `kind-experiment` workflow (`policy=both`) and add the run URL to `docs/methodology.md`.

## Hypothesis decisions

**H1 (rejected).** Predictive scaling reduces SLO violations on ramp and regime-shift workloads because it can allocate capacity before HPA observes high CPU.

> predictive did not lower the mean violation rate with >=4/5 seeds agreeing in any rising or regime-shift scenario

**H2 (supported).** Predictive scaling uses more replica-seconds when its upper quantile is poorly calibrated.

> predictive uses more replica-steps than HPA on: spike, ramp

**H3 (supported).** Forecast MAE and SLO violation rate do not have a strictly monotonic relationship.

> Spearman(MAE, violation rate) = 0.050, |rho| < 0.8

**H4 (inconclusive).** Periodic expanding-window retraining helps after drift but does not dominate reactive HPA in every scenario.

> retrained and frozen predictive tie on every seed after drift (no violations either way), so retraining's effect cannot be measured here

## Threats to validity

- Offline latency comes from an analytic overload curve, not measurement.
- The kind experiment runs on a shared, ephemeral GitHub VM.
- CPU metrics from Metrics Server have sampling delay.
- Four generated workload shapes do not represent every production service.
- One-node AKS validation checks portability, not production scale.

## Reproduction

```bash
pip install -e '.[dev,service]'
python -m pytest -q
python -m autoscaler_lab.cli run-offline --config configs/experiment.json --output results/offline
python -m autoscaler_lab.cli render-report --summary results/offline/summary.json --output docs/results.md
```

## Appendix: raw runs

| Scenario | Policy | Seed | SLO viol. | Replica-steps | Scaling events | Oscillations | Forecast MAE | Fallbacks |
|---|---|---|---|---|---|---|---|---|
| ramp | hpa | 42 | 0.000 | 450 | 5 | 0 | - | 0 |
| ramp | hpa | 43 | 0.000 | 453 | 5 | 0 | - | 0 |
| ramp | hpa | 44 | 0.000 | 451 | 5 | 0 | - | 0 |
| ramp | hpa | 45 | 0.000 | 448 | 5 | 0 | - | 0 |
| ramp | hpa | 46 | 0.000 | 451 | 5 | 0 | - | 0 |
| ramp | oracle | 42 | 0.000 | 486 | 5 | 0 | 0.000 | 0 |
| ramp | oracle | 43 | 0.000 | 487 | 11 | 6 | 0.000 | 0 |
| ramp | oracle | 44 | 0.000 | 484 | 9 | 4 | 0.000 | 0 |
| ramp | oracle | 45 | 0.000 | 485 | 7 | 2 | 0.000 | 0 |
| ramp | oracle | 46 | 0.000 | 484 | 7 | 2 | 0.000 | 0 |
| ramp | predictive | 42 | 0.000 | 461 | 7 | 2 | 10.529 | 30 |
| ramp | predictive | 43 | 0.000 | 462 | 5 | 0 | 10.490 | 30 |
| ramp | predictive | 44 | 0.000 | 464 | 7 | 2 | 10.706 | 30 |
| ramp | predictive | 45 | 0.000 | 463 | 7 | 2 | 10.705 | 30 |
| ramp | predictive | 46 | 0.000 | 462 | 9 | 4 | 10.394 | 30 |
| ramp | predictive_frozen | 42 | 0.000 | 332 | 4 | 2 | 31.256 | 30 |
| ramp | predictive_frozen | 43 | 0.000 | 333 | 2 | 0 | 31.295 | 30 |
| ramp | predictive_frozen | 44 | 0.000 | 335 | 4 | 2 | 30.872 | 30 |
| ramp | predictive_frozen | 45 | 0.000 | 334 | 4 | 2 | 31.343 | 30 |
| ramp | predictive_frozen | 46 | 0.000 | 333 | 6 | 4 | 31.234 | 30 |
| ramp | static | 42 | 0.000 | 358 | 1 | 0 | - | 0 |
| ramp | static | 43 | 0.000 | 358 | 1 | 0 | - | 0 |
| ramp | static | 44 | 0.000 | 358 | 1 | 0 | - | 0 |
| ramp | static | 45 | 0.000 | 358 | 1 | 0 | - | 0 |
| ramp | static | 46 | 0.000 | 358 | 1 | 0 | - | 0 |
| regime_shift | hpa | 42 | 0.000 | 416 | 2 | 0 | - | 0 |
| regime_shift | hpa | 43 | 0.000 | 416 | 2 | 0 | - | 0 |
| regime_shift | hpa | 44 | 0.000 | 416 | 2 | 0 | - | 0 |
| regime_shift | hpa | 45 | 0.000 | 416 | 2 | 0 | - | 0 |
| regime_shift | hpa | 46 | 0.000 | 416 | 2 | 0 | - | 0 |
| regime_shift | oracle | 42 | 0.000 | 419 | 2 | 0 | 0.000 | 0 |
| regime_shift | oracle | 43 | 0.000 | 419 | 2 | 0 | 0.000 | 0 |
| regime_shift | oracle | 44 | 0.000 | 419 | 2 | 0 | 0.000 | 0 |
| regime_shift | oracle | 45 | 0.000 | 419 | 2 | 0 | 0.000 | 0 |
| regime_shift | oracle | 46 | 0.000 | 419 | 2 | 0 | 0.000 | 0 |
| regime_shift | predictive | 42 | 0.000 | 380 | 2 | 0 | 5.824 | 30 |
| regime_shift | predictive | 43 | 0.000 | 380 | 2 | 0 | 7.099 | 30 |
| regime_shift | predictive | 44 | 0.000 | 353 | 4 | 2 | 8.791 | 30 |
| regime_shift | predictive | 45 | 0.000 | 380 | 2 | 0 | 5.955 | 30 |
| regime_shift | predictive | 46 | 0.000 | 380 | 2 | 0 | 7.475 | 30 |
| regime_shift | predictive_frozen | 42 | 0.000 | 239 | 1 | 0 | 23.811 | 30 |
| regime_shift | predictive_frozen | 43 | 0.000 | 239 | 1 | 0 | 24.304 | 30 |
| regime_shift | predictive_frozen | 44 | 0.000 | 239 | 1 | 0 | 24.027 | 30 |
| regime_shift | predictive_frozen | 45 | 0.000 | 239 | 1 | 0 | 24.286 | 30 |
| regime_shift | predictive_frozen | 46 | 0.000 | 239 | 1 | 0 | 24.105 | 30 |
| regime_shift | static | 42 | 0.000 | 358 | 1 | 0 | - | 0 |
| regime_shift | static | 43 | 0.000 | 358 | 1 | 0 | - | 0 |
| regime_shift | static | 44 | 0.000 | 358 | 1 | 0 | - | 0 |
| regime_shift | static | 45 | 0.000 | 358 | 1 | 0 | - | 0 |
| regime_shift | static | 46 | 0.000 | 358 | 1 | 0 | - | 0 |
| spike | hpa | 42 | 0.008 | 172 | 7 | 4 | - | 0 |
| spike | hpa | 43 | 0.008 | 178 | 17 | 15 | - | 0 |
| spike | hpa | 44 | 0.008 | 185 | 13 | 11 | - | 0 |
| spike | hpa | 45 | 0.008 | 178 | 9 | 7 | - | 0 |
| spike | hpa | 46 | 0.008 | 175 | 13 | 11 | - | 0 |
| spike | oracle | 42 | 0.000 | 219 | 52 | 49 | 0.000 | 0 |
| spike | oracle | 43 | 0.000 | 222 | 59 | 57 | 0.000 | 0 |
| spike | oracle | 44 | 0.000 | 229 | 64 | 62 | 0.000 | 0 |
| spike | oracle | 45 | 0.000 | 217 | 50 | 48 | 0.000 | 0 |
| spike | oracle | 46 | 0.000 | 221 | 53 | 51 | 0.000 | 0 |
| spike | predictive | 42 | 0.075 | 323 | 18 | 16 | 7.051 | 30 |
| spike | predictive | 43 | 0.075 | 350 | 29 | 27 | 7.323 | 30 |
| spike | predictive | 44 | 0.075 | 327 | 15 | 13 | 7.400 | 30 |
| spike | predictive | 45 | 0.075 | 344 | 31 | 27 | 8.102 | 30 |
| spike | predictive | 46 | 0.075 | 339 | 15 | 13 | 7.262 | 30 |
| spike | predictive_frozen | 42 | 0.083 | 239 | 1 | 0 | 7.040 | 30 |
| spike | predictive_frozen | 43 | 0.083 | 239 | 1 | 0 | 7.205 | 30 |
| spike | predictive_frozen | 44 | 0.083 | 239 | 1 | 0 | 7.132 | 30 |
| spike | predictive_frozen | 45 | 0.083 | 239 | 1 | 0 | 7.125 | 30 |
| spike | predictive_frozen | 46 | 0.083 | 239 | 1 | 0 | 7.103 | 30 |
| spike | static | 42 | 0.000 | 358 | 1 | 0 | - | 0 |
| spike | static | 43 | 0.000 | 358 | 1 | 0 | - | 0 |
| spike | static | 44 | 0.000 | 358 | 1 | 0 | - | 0 |
| spike | static | 45 | 0.000 | 358 | 1 | 0 | - | 0 |
| spike | static | 46 | 0.000 | 358 | 1 | 0 | - | 0 |
| steady | hpa | 42 | 0.000 | 239 | 1 | 0 | - | 0 |
| steady | hpa | 43 | 0.000 | 238 | 3 | 2 | - | 0 |
| steady | hpa | 44 | 0.000 | 239 | 1 | 0 | - | 0 |
| steady | hpa | 45 | 0.000 | 239 | 1 | 0 | - | 0 |
| steady | hpa | 46 | 0.000 | 238 | 3 | 2 | - | 0 |
| steady | oracle | 42 | 0.000 | 239 | 1 | 0 | 0.000 | 0 |
| steady | oracle | 43 | 0.000 | 238 | 3 | 2 | 0.000 | 0 |
| steady | oracle | 44 | 0.000 | 239 | 1 | 0 | 0.000 | 0 |
| steady | oracle | 45 | 0.000 | 239 | 1 | 0 | 0.000 | 0 |
| steady | oracle | 46 | 0.000 | 238 | 3 | 2 | 0.000 | 0 |
| steady | predictive | 42 | 0.000 | 239 | 1 | 0 | 1.306 | 30 |
| steady | predictive | 43 | 0.000 | 239 | 1 | 0 | 1.705 | 30 |
| steady | predictive | 44 | 0.000 | 239 | 1 | 0 | 1.757 | 30 |
| steady | predictive | 45 | 0.000 | 239 | 1 | 0 | 1.698 | 30 |
| steady | predictive | 46 | 0.000 | 239 | 1 | 0 | 1.471 | 30 |
| steady | predictive_frozen | 42 | 0.000 | 239 | 1 | 0 | 1.304 | 30 |
| steady | predictive_frozen | 43 | 0.000 | 239 | 1 | 0 | 1.663 | 30 |
| steady | predictive_frozen | 44 | 0.000 | 239 | 1 | 0 | 1.742 | 30 |
| steady | predictive_frozen | 45 | 0.000 | 239 | 1 | 0 | 1.646 | 30 |
| steady | predictive_frozen | 46 | 0.000 | 239 | 1 | 0 | 1.455 | 30 |
| steady | static | 42 | 0.000 | 358 | 1 | 0 | - | 0 |
| steady | static | 43 | 0.000 | 358 | 1 | 0 | - | 0 |
| steady | static | 44 | 0.000 | 358 | 1 | 0 | - | 0 |
| steady | static | 45 | 0.000 | 358 | 1 | 0 | - | 0 |
| steady | static | 46 | 0.000 | 358 | 1 | 0 | - | 0 |
