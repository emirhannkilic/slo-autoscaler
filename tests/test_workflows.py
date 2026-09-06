"""Structural checks on the GitHub Actions workflows. The real behaviour
runs on GitHub -- these only catch YAML and wiring mistakes locally.
"""

from pathlib import Path

import yaml

WF_DIR = Path(".github/workflows")


def _load(name):
    # PyYAML parses the workflow `on:` key as the boolean True; that is fine,
    # we only assert on the parts we care about.
    return yaml.safe_load((WF_DIR / name).read_text())


def test_ci_runs_tests_and_offline_matrix():
    ci = _load("ci.yml")
    steps = ci["jobs"]["test-and-offline"]["steps"]
    run_cmds = " ".join(s.get("run", "") for s in steps)
    assert "pytest -q" in run_cmds
    assert "run-offline" in run_cmds
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact"))
    assert upload["if"] == "success()"
    assert upload["with"]["if-no-files-found"] == "error"


def test_ci_has_least_privilege():
    ci = _load("ci.yml")
    assert ci["permissions"] == {"contents": "read"}


def test_kind_workflow_is_manual_with_policy_choice():
    wf = _load("kind-experiment.yml")
    dispatch = wf[True]["workflow_dispatch"]  # `on:` -> True
    options = dispatch["inputs"]["policy"]["options"]
    assert options == ["hpa", "predictive", "both"]


def test_kind_workflow_pins_kind_version_and_bounds_runtime():
    wf = _load("kind-experiment.yml")
    job = wf["jobs"]["live"]
    assert job["timeout-minutes"] == 40
    # matrix is built dynamically from the dispatch input by the `plan` job
    assert job["needs"] == "plan"
    assert "fromJSON(needs.plan.outputs.policies)" in job["strategy"]["matrix"]["policy"]
    plan_run = wf["jobs"]["plan"]["steps"][0]["run"]
    assert '["hpa","predictive"]' in plan_run
    run_cmds = " ".join(s.get("run", "") for s in job["steps"])
    assert "v0.33.0" in run_cmds
    assert "run_live_experiment.sh" in run_cmds


def test_kind_workflow_always_uploads_diagnostics():
    wf = _load("kind-experiment.yml")
    steps = wf["jobs"]["live"]["steps"]
    upload = next(s for s in steps if s.get("uses", "").startswith("actions/upload-artifact"))
    assert upload["if"] == "always()"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["path"] == "results/live/**"


def test_no_cloud_credentials_referenced():
    for name in ("ci.yml", "kind-experiment.yml"):
        text = (WF_DIR / name).read_text().lower()
        for token in ("azure", "aws", "client_secret", "credentials"):
            assert token not in text, f"{name} references {token}"
