import pytest

from autoscaler_lab.controller import (
    _Loop,
    build_scale_command,
    decide_replicas,
    parse_cpu_millicores,
)


def test_parse_kubectl_top_cpu():
    text = "load-target-a 75m 80Mi\nload-target-b 110m 82Mi\n"
    assert parse_cpu_millicores(text) == [75, 110]


def test_parse_whole_cores_as_millicores():
    assert parse_cpu_millicores("pod-a 1 50Mi\npod-b 2 60Mi\n") == [1000, 2000]


def test_empty_cpu_metrics_fail():
    with pytest.raises(ValueError, match="cpu metrics"):
        parse_cpu_millicores("")


def test_malformed_row_fails_rather_than_zero():
    with pytest.raises(ValueError):
        parse_cpu_millicores("load-target-a not-a-number 80Mi\n")


def test_scale_command_has_explicit_target():
    command = build_scale_command("default", "load-target", 3)
    assert command == [
        "kubectl", "scale", "deployment/load-target",
        "--namespace", "default", "--replicas", "3",
    ]


def test_decide_replicas_uses_upper_forecast_and_clamps():
    # per-replica budget 60 millicores; upper forecast 200 -> ceil(200/60) = 4
    assert decide_replicas(upper_millicores=200, per_replica_millicores=60,
                           min_replicas=1, max_replicas=6) == 4
    # huge forecast clamps to max
    assert decide_replicas(5000, 60, 1, 6) == 6
    # tiny forecast clamps to min
    assert decide_replicas(10, 60, 1, 6) == 1


def test_loop_warms_up_from_persistence_to_a_trained_model():
    loop = _Loop(per_replica_millicores=60, min_replicas=1, max_replicas=6, refit_every=6)
    records = []
    # 96 ticks of a repeating ramp, like the 24-minute live workload
    ramp = [40, 60, 120, 45] * 24
    for i, cpu in enumerate(ramp):
        records.append(loop.step(cpu_total=cpu * 2, active_replicas=records[-1]["requested_replicas"] if records else 1))

    assert records[0]["fallback_used"] is True  # no model yet
    assert records[0]["history_size"] == 1
    non_fallback = [r for r in records if not r["fallback_used"]]
    assert len(non_fallback) >= 20  # model warmed up and stayed trained
    assert all(1 <= r["requested_replicas"] <= 6 for r in records)
