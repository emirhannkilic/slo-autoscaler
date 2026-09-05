"""Thin wrapper -- the orchestration lives in ``autoscaler_lab.experiment``
so it is importable and testable. Run: ``python experiments/run_matrix.py``.
"""

from pathlib import Path

from autoscaler_lab.experiment import run_matrix

if __name__ == "__main__":
    run_matrix(Path("configs/experiment.json"), Path("results/offline"))
