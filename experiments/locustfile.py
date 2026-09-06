"""Load shape for the live kind experiments.

One cycle is four equal 90s stages: 15 -> 60 -> 120 -> 20 users. The cycle
repeats 4 times (24 minutes total) so the predictive controller collects
enough history (>= 30 samples at a 15s interval) to train its quantile model
instead of running on persistence the whole time. Zero wait time, so CPU is
the limiting resource. HPA runs use the identical shape.

Run headless from run_live_experiment.sh:
    locust -f experiments/locustfile.py --headless --host http://localhost:18080 \
        --csv results/live/<policy>/locust
"""

from locust import HttpUser, LoadTestShape, task

_STAGE_SECONDS = 90
_STAGES = [15, 60, 120, 20]
_CYCLES = 4


class WorkUser(HttpUser):
    wait_time = lambda self: 0  # noqa: E731 -- back-to-back requests

    @task
    def work(self):
        self.client.get("/work", name="/work")


class FourStageShape(LoadTestShape):
    def tick(self):
        run_time = self.get_run_time()
        stage = int(run_time // _STAGE_SECONDS)
        if stage >= len(_STAGES) * _CYCLES:
            return None
        users = _STAGES[stage % len(_STAGES)]
        return users, users  # (user_count, spawn_rate)
