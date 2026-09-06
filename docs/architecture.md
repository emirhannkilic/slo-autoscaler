# Architecture

## The decision loop under test

```
workload -> observation -> forecast -> scaling decision -> system response
                                                        -> latency and resource cost
```

Every policy is evaluated on the full loop, not on forecast accuracy alone.

## Offline

`autoscaler_lab` is a src-layout Python package. The offline path has no
Docker, no Kubernetes, and no network.

| Module | Responsibility |
|---|---|
| `models.py` | Frozen domain records: `WorkloadPoint`, `SystemState`, `Forecast`, `ScalingDecision`. |
| `workload.py` | Deterministic scenarios (steady, spike, ramp, regime_shift) from an isolated RNG. |
| `metrics.py` | `ServiceModel` (analytic overload curve) and `summarize` (experiment metrics, no blended score). |
| `forecast.py` | `PersistenceForecaster`, `QuantileForecaster` (gradient-boosted quantile regression), `OracleForecaster`. Only the oracle sees the future. |
| `policies.py` | `StaticPolicy`, `HpaPolicy` (Kubernetes-style CPU ratio), `PredictivePolicy` (size for the upper quantile). All bounded to `[1, 6]`. |
| `simulator.py` | One-step-delayed closed loop. A decision made at step `t` takes effect at `t + 1`. |
| `experiment.py` | The 4 x 5 x 5 run matrix; writes JSON and two plots. |
| `report.py` | Fixed-rule hypothesis decisions and the `results.md` renderer. |
| `cli.py` | `run-offline` and `render-report`. |

The `predictive_frozen` policy is `PredictivePolicy` with `refit_every = 0`:
the quantile model trains once when history first reaches 30 points and is
never refit. It exists so H4 can compare retrained vs frozen after drift.

## Live

The same idea on a real Kubernetes control loop, run only inside GitHub
Actions on an ephemeral `kind` cluster.

| Piece | Role |
|---|---|
| `service/app.py` | CPU-bound FastAPI target. `GET /work?rounds=N` chains SHA-256 so load shows up as real pod CPU. |
| `service/Dockerfile` | `python:3.12-slim`, non-root user. |
| `infra/kind/*.yaml` | One-node cluster, deployment (CPU request 100m / limit 500m), NodePort service, HPA (min 1, max 6, target 60% -- identical to the offline `HpaPolicy`). |
| `experiments/locustfile.py` | Four 90s stages (15 -> 60 -> 120 -> 20 users), repeated 4 times (24 minutes) so the controller's quantile model can warm up. |
| `src/autoscaler_lab/controller.py` | The live predictive controller. Reads CPU from `kubectl top`, forecasts total pod CPU, sizes for the upper quantile, applies with `kubectl scale`. Stops after three consecutive metric failures. |
| `infra/kind/run_live_experiment.sh` | Fail-fast orchestration. Collects diagnostics and deletes the cluster on every exit. |

For `hpa` runs the script applies `hpa.yaml` and lets Kubernetes scale. For
`predictive` runs it does not apply `hpa.yaml`; the controller runs instead,
and the run must produce at least 20 decisions from a trained model (not
persistence fallback) or it fails.

## What is deliberately excluded

Node autoscaling, multi-cluster orchestration, production SLA claims, a hosted
demo, auth, dashboards, RL policies, and a custom operator or CRD.
