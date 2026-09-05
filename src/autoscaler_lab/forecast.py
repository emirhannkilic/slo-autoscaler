"""Persistence, causal quantile, and oracle demand forecasts. No replica logic.

Every forecaster exposes ``fit(history)`` and ``predict(history, step)``.
Only ``OracleForecaster`` may see future demand; the others read history only.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from autoscaler_lab.models import Forecast, WorkloadPoint

_LAGS = (1, 2, 3, 6, 12)
_MAX_LAG = max(_LAGS)


class PersistenceForecaster:
    """Predict the last observed value, widened by a safety margin."""

    def __init__(self, safety_margin: float = 0.20) -> None:
        self.safety_margin = safety_margin

    def fit(self, history: Sequence[float]) -> None:  # nothing to learn
        pass

    def predict(self, history: Sequence[float], step: int) -> Forecast:
        last = float(history[-1])
        return Forecast.make(last, last * (1.0 + self.safety_margin))


def _features(window: Sequence[float]) -> list[float]:
    """Lag features from past values only. ``window`` ends at the step to predict from."""
    recent6 = window[-6:]
    return [
        window[-1],
        window[-2],
        window[-3],
        window[-6],
        window[-12],
        float(np.mean(recent6)),
        float(np.std(recent6)),
        window[-1] - window[-6],
    ]


class QuantileForecaster:
    """Gradient-boosted quantile regression: median point + 0.9 upper bound.

    Falls back to persistence before ``min_train_points`` observations or when
    a model returns a non-finite number.
    """

    def __init__(
        self,
        lags: tuple[int, ...] = _LAGS,
        min_train_points: int = 30,
        safety_margin: float = 0.20,
    ) -> None:
        self.min_train_points = min_train_points
        self._fallback = PersistenceForecaster(safety_margin)
        self._median: HistGradientBoostingRegressor | None = None
        self._upper: HistGradientBoostingRegressor | None = None

    def fit(self, history: Sequence[float]) -> None:
        history = [float(x) for x in history]
        if len(history) < self.min_train_points:
            self._median = self._upper = None
            return

        rows, targets = [], []
        for t in range(_MAX_LAG, len(history)):
            rows.append(_features(history[:t]))
            targets.append(history[t])
        x = np.asarray(rows)
        y = np.asarray(targets)

        self._median = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.5, random_state=0
        ).fit(x, y)
        self._upper = HistGradientBoostingRegressor(
            loss="quantile", quantile=0.9, random_state=0
        ).fit(x, y)

    def predict(self, history: Sequence[float], step: int) -> Forecast:
        history = [float(x) for x in history]
        if (
            self._median is None
            or self._upper is None
            or len(history) < _MAX_LAG
        ):
            return self._fallback.predict(history, step)

        x = np.asarray([_features(history)])
        point = float(self._median.predict(x)[0])
        upper = float(self._upper.predict(x)[0])
        if not (math.isfinite(point) and math.isfinite(upper)):
            return self._fallback.predict(history, step)
        return Forecast.make(point, upper)


class OracleForecaster:
    """Upper-bound reference: returns the exact next demand value.

    This is the only forecaster with access to future workload.
    """

    def __init__(self, workload: Sequence[WorkloadPoint]) -> None:
        self._demand = [p.demand_rps for p in workload]

    def fit(self, history: Sequence[float]) -> None:
        pass

    def predict(self, history: Sequence[float], step: int) -> Forecast:
        value = float(self._demand[step])
        return Forecast.make(value, value)
