# Methodology

Full detail is written in Task 11. This file currently holds only the
reproducibility evidence links so the workflows can be cited.

## Reproducibility evidence

### Offline study

One command from a clean Python 3.12 environment:

```bash
pip install -e '.[dev,service]'
python -m autoscaler_lab.cli run-offline --config configs/experiment.json --output results/offline
```

### Live kind experiment

Triggered manually from the Actions tab (`kind-experiment` workflow,
`policy=both`). Each run builds the service image, creates an ephemeral kind
cluster, installs Metrics Server, runs the 24-minute Locust workload, and
uploads results plus diagnostics.

Successful runs:

- HPA: _(add the Actions run URL here after the first green run)_
- Predictive: _(add the Actions run URL here after the first green run)_

A status badge is added only after the workflow has passed once.
