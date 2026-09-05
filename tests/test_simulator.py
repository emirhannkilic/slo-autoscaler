from autoscaler_lab.forecast import OracleForecaster, PersistenceForecaster
from autoscaler_lab.metrics import ServiceModel, summarize
from autoscaler_lab.models import Forecast
from autoscaler_lab.policies import HpaPolicy, PredictivePolicy, StaticPolicy
from autoscaler_lab.simulator import run_simulation
from autoscaler_lab.workload import generate_workload

WORKLOAD = generate_workload("spike", steps=40, seed=42)
HPA = HpaPolicy(target_cpu=60, min_replicas=1, max_replicas=6)
STATIC = StaticPolicy(replicas=2)
PREDICTIVE = PredictivePolicy(
    capacity_per_replica=25, target_utilization=0.60, min_replicas=1, max_replicas=6
)
PERSISTENCE = PersistenceForecaster(0.20)


class HistoryLengthSpyForecaster:
    last_was_fallback = False

    def __init__(self):
        self.seen_lengths = []
        self.fit_calls = 0

    def fit(self, history):
        self.fit_calls += 1

    def predict(self, history, step):
        self.seen_lengths.append(len(history))
        return Forecast.make(history[-1], history[-1] * 1.2)


def test_scaling_decision_applies_on_next_step():
    states = run_simulation(WORKLOAD, HPA, PERSISTENCE, ServiceModel(), initial_replicas=1)
    assert states[0].replicas == 1
    assert states[1].replicas == states[0].decision_replicas


def test_normal_forecaster_never_receives_future_values():
    spy = HistoryLengthSpyForecaster()
    run_simulation(WORKLOAD, PREDICTIVE, spy, ServiceModel())
    assert spy.seen_lengths == list(range(1, len(WORKLOAD) + 1))


def test_simulation_emits_one_state_per_workload_point():
    states = run_simulation(WORKLOAD, STATIC, PERSISTENCE, ServiceModel())
    assert len(states) == len(WORKLOAD)


def test_final_state_decision_equals_active_replicas():
    states = run_simulation(WORKLOAD, HPA, PERSISTENCE, ServiceModel())
    assert states[-1].decision_replicas == states[-1].replicas


def test_non_predictive_policy_never_calls_the_forecaster():
    spy = HistoryLengthSpyForecaster()
    for policy in (STATIC, HPA):
        states = run_simulation(WORKLOAD, policy, spy, ServiceModel())
        assert all(s.forecast_rps is None for s in states)
        assert all(s.fallback_used is False for s in states)
    assert spy.seen_lengths == []
    assert spy.fit_calls == 0
    result = summarize(states, "hpa", "spike", 42)
    assert result.forecast_mae is None


def test_oracle_forecast_mae_is_zero():
    workload = generate_workload("ramp", steps=120, seed=42)
    states = run_simulation(workload, PREDICTIVE, OracleForecaster(workload), ServiceModel())
    result = summarize(states, "oracle", "ramp", 42)
    assert result.forecast_mae == 0.0


def test_empty_workload_fails():
    try:
        run_simulation([], STATIC, PERSISTENCE, ServiceModel())
    except ValueError:
        pass
    else:
        raise AssertionError("empty workload must fail")
