from autoscaler_lab.workload import generate_workload


def test_workload_is_reproducible():
    first = generate_workload("spike", steps=60, seed=42)
    second = generate_workload("spike", steps=60, seed=42)
    assert first == second


def test_workload_never_has_negative_demand():
    for kind in ("steady", "spike", "ramp", "regime_shift"):
        assert all(p.demand_rps >= 0 for p in generate_workload(kind, 60, 42))


def test_unknown_workload_fails():
    try:
        generate_workload("random-name", 60, 42)
    except ValueError as exc:
        assert "unknown workload" in str(exc).lower()
    else:
        raise AssertionError("unknown workload must fail")
