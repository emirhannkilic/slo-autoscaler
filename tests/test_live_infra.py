"""Static checks for the live-experiment infra. No Docker or kind here --
the first real run happens in GitHub Actions (Task 10).
"""

import subprocess
import sys
from pathlib import Path

import yaml

KIND_DIR = Path("infra/kind")


def _load(name):
    return yaml.safe_load((KIND_DIR / name).read_text())


def test_hpa_matches_offline_policy_bounds():
    hpa = _load("hpa.yaml")
    assert hpa["spec"]["minReplicas"] == 1
    assert hpa["spec"]["maxReplicas"] == 6
    metric = hpa["spec"]["metrics"][0]["resource"]
    assert metric["name"] == "cpu"
    assert metric["target"]["averageUtilization"] == 60


def test_deployment_has_cpu_request_and_health_probes():
    container = _load("deployment.yaml")["spec"]["template"]["spec"]["containers"][0]
    assert container["resources"]["requests"]["cpu"] == "100m"
    assert container["resources"]["limits"]["cpu"] == "500m"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health"
    assert container["livenessProbe"]["httpGet"]["path"] == "/health"


def test_service_and_cluster_agree_on_nodeport():
    svc_nodeport = _load("service.yaml")["spec"]["ports"][0]["nodePort"]
    mapping = _load("cluster.yaml")["nodes"][0]["extraPortMappings"][0]
    assert svc_nodeport == mapping["containerPort"] == 30080
    assert mapping["hostPort"] == 18080


def test_app_label_is_consistent():
    for name in ("deployment.yaml", "service.yaml"):
        doc = _load(name)
        assert doc["metadata"]["labels"]["app"] == "load-target"


def test_locustfile_defines_four_stage_shape():
    # importing locust monkey-patches ssl/threading via gevent, which
    # deadlocks pytest when other test modules use native threads (sklearn).
    # run this import in its own interpreter instead.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from experiments.locustfile import FourStageShape, WorkUser, _STAGES, _CYCLES; "
            "assert _STAGES == [15, 60, 120, 20]; "
            "assert _CYCLES == 4; "
            "s = FourStageShape(); "
            "assert s.tick() == (15, 15); "
            "assert WorkUser.wait_time is not None; "
            "print('ok')",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_experiment_script_has_valid_bash_syntax():
    result = subprocess.run(
        ["bash", "-n", str(KIND_DIR / "run_live_experiment.sh")],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_experiment_script_cleans_up_on_every_exit():
    text = (KIND_DIR / "run_live_experiment.sh").read_text()
    assert "trap collect_and_cleanup EXIT" in text
    assert "kind delete cluster" in text


def test_predictive_branch_starts_controller_and_checks_warmup():
    text = (KIND_DIR / "run_live_experiment.sh").read_text()
    assert "autoscaler_lab.controller" in text
    # predictive runs must prove the quantile model warmed up
    assert '"fallback_used": false' in text
    assert "-ge 20" in text
    # hpa.yaml must NOT be applied in the predictive branch
    assert 'if [[ "$POLICY" == "hpa" ]]; then\n  kubectl apply -f "${KIND_DIR}/hpa.yaml"' in text
