from autoscaler_lab.metrics import ServiceModel, _count_oscillations, summarize
from autoscaler_lab.models import SystemState


def test_more_replicas_reduce_utilization_and_latency():
    model = ServiceModel()
    cpu_one, latency_one = model.observe(demand_rps=50, replicas=1)
    cpu_four, latency_four = model.observe(demand_rps=50, replicas=4)
    assert cpu_four < cpu_one
    assert latency_four < latency_one


def test_summary_counts_slo_violations_and_replica_steps():
    states = [
        SystemState(0, 10, 1, 40, 50, None, None, False),
        SystemState(1, 80, 2, 160, 250, None, None, False),
    ]
    result = summarize(states, policy="hpa", scenario="spike", seed=42)
    assert result.slo_violation_rate == 0.5
    assert result.replica_steps == 3


def test_oscillation_counts_sign_changes_in_nonzero_deltas():
    assert _count_oscillations([1, 2, 3, 4]) == 0  # monotone: no sign change
    assert _count_oscillations([2, 2, 2]) == 0  # zero deltas ignored
    assert _count_oscillations([1, 3, 2, 4, 4, 2]) == 3  # +,-,+,(0),-  -> 3 flips
