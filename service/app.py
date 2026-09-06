"""Deliberately CPU-bound HTTP target for live autoscaling experiments.

``/work`` burns CPU with chained SHA-256 rounds -- no I/O, no external calls,
no stored request data. Load on this endpoint shows up as real pod CPU, which
is what Kubernetes HPA and the predictive controller scale on.
"""

from __future__ import annotations

import hashlib
import os
import time
from typing import Annotated

from fastapi import FastAPI, Query

_MIN_ROUNDS = 100
_MAX_ROUNDS = 50_000
_DEFAULT_ROUNDS = int(os.environ.get("DEFAULT_WORK_ROUNDS", "3000"))

app = FastAPI(title="autoscaler load target")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/work")
def work(
    rounds: Annotated[int, Query(ge=_MIN_ROUNDS, le=_MAX_ROUNDS)] = _DEFAULT_ROUNDS,
) -> dict[str, object]:
    start = time.perf_counter()
    digest = b"autoscaler-lab"
    for _ in range(rounds):
        digest = hashlib.sha256(digest).digest()
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return {"digest": digest.hex(), "elapsed_ms": elapsed_ms}
