from pathlib import Path

import pytest

from autoscaler_lab.experiment import run_matrix

CONFIG = Path("configs/experiment.json")


@pytest.fixture(scope="module")
def matrix(tmp_path_factory):
    out = tmp_path_factory.mktemp("offline")
    return run_matrix(CONFIG, out), out


def test_matrix_produces_every_scenario_policy_seed(matrix):
    summaries, _ = matrix
    assert len(summaries) == 4 * 5 * 5  # 4 scenarios, 5 policies, 5 seeds
    assert all(0 <= row.slo_violation_rate <= 1 for row in summaries)
    assert all(row.replica_steps >= 120 for row in summaries)
    assert {row.policy for row in summaries} == {
        "static", "hpa", "predictive", "predictive_frozen", "oracle"
    }


def test_matrix_writes_summary_and_plots(matrix):
    _, out = matrix
    assert (out / "summary.json").is_file()
    assert (out / "pareto.png").stat().st_size > 0
    assert (out / "forecast_vs_slo.png").stat().st_size > 0
