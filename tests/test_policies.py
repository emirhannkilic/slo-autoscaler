from autoscaler_lab.models import Forecast, SystemState
from autoscaler_lab.policies import HpaPolicy, PredictivePolicy, StaticPolicy


CURRENT = SystemState(0, 40, 2, 90, 120, None, None, False)


def test_static_policy_never_changes():
    assert StaticPolicy(replicas=2).decide(CURRENT, None).replicas == 2


def test_hpa_scales_up_on_high_cpu():
    decision = HpaPolicy(target_cpu=60, min_replicas=1, max_replicas=6).decide(CURRENT, None)
    assert decision.replicas == 3


def test_predictive_policy_uses_upper_quantile():
    policy = PredictivePolicy(
        capacity_per_replica=25, target_utilization=0.60, min_replicas=1, max_replicas=6
    )
    decision = policy.decide(CURRENT, Forecast(point=50, upper=80))
    assert decision.replicas == 6


def test_every_policy_clamps_replica_count():
    forecast = Forecast(point=1000, upper=1000)
    policy = PredictivePolicy(25, 0.60, 1, 6)
    assert policy.decide(CURRENT, forecast).replicas == 6


def test_predictive_policy_requires_a_forecast():
    policy = PredictivePolicy(25, 0.60, 1, 6)
    try:
        policy.decide(CURRENT, None)
    except ValueError as exc:
        assert "forecast" in str(exc).lower()
    else:
        raise AssertionError("predictive policy must reject a missing forecast")
