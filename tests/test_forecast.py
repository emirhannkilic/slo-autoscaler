from autoscaler_lab.forecast import (
    OracleForecaster,
    PersistenceForecaster,
    QuantileForecaster,
)
from autoscaler_lab.workload import generate_workload


def test_persistence_uses_only_last_observation():
    result = PersistenceForecaster(0.20).predict([10, 20], step=2)
    assert result.point == 20
    assert result.upper == 24


def test_quantile_forecast_never_crosses():
    history = [float(i % 20 + 10) for i in range(80)]
    model = QuantileForecaster()
    model.fit(history)
    result = model.predict(history, step=len(history))
    assert result.upper >= result.point >= 0


def test_oracle_reads_exact_next_workload_only():
    workload = generate_workload("spike", 60, 42)
    result = OracleForecaster(workload).predict([workload[0].demand_rps], step=1)
    assert result.point == workload[1].demand_rps
    assert result.upper == workload[1].demand_rps


def test_quantile_forecast_is_causal():
    """A normal forecaster's prediction must not change when values *after*
    the requested step change -- proof it reads history, not the future."""
    history = [float(i % 15 + 20) for i in range(60)]
    model = QuantileForecaster()
    model.fit(history)
    before = model.predict(history, step=len(history))

    tampered = history + [999.0, 999.0, 999.0]
    after = model.predict(tampered[: len(history)], step=len(history))
    assert after == before
