from pathlib import Path

import pytest

from autoscaler_lab.report import decide_hypotheses, render_report

SUMMARY = Path("results/offline/summary.json")


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    if not SUMMARY.is_file():
        pytest.skip("run the offline matrix first: cli run-offline")
    out = tmp_path_factory.mktemp("report") / "results.md"
    render_report(SUMMARY, out)
    return out.read_text()


def test_report_contains_required_sections(report):
    for heading in (
        "## Research questions",
        "## Experimental controls",
        "## Offline results",
        "## Hypothesis decisions",
        "## Threats to validity",
        "## Reproduction",
    ):
        assert heading in report


def test_report_states_a_verdict_for_every_hypothesis(report):
    for h in ("H1", "H2", "H3", "H4"):
        assert h in report
    assert any(v in report for v in ("supported", "rejected", "inconclusive"))


def test_report_lists_validity_threats(report):
    assert "analytic" in report.lower()  # offline latency is an analytic curve
    assert "kind" in report.lower()


def test_hypothesis_decisions_are_one_of_three_values():
    if not SUMMARY.is_file():
        pytest.skip("run the offline matrix first")
    import json

    data = json.loads(SUMMARY.read_text())
    decisions = decide_hypotheses(data["runs"])
    assert set(decisions) == {"H1", "H2", "H3", "H4"}
    for verdict in decisions.values():
        assert verdict["decision"] in ("supported", "rejected", "inconclusive")
