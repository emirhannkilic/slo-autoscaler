"""Load shape for the live kind experiments: four equal 90s stages
15 -> 60 -> 120 -> 20 users. Zero wait time, so CPU is the limiting resource.

Run headless from run_live_experiment.sh:
    locust -f experiments/locustfile.py --headless --host http://localhost:18080 \
        --csv results/live/<policy>/locust
"""

from locust import HttpUser, LoadTestShape, task

_STAGE_SECONDS = 90
_STAGES = [15, 60, 120, 20]


class WorkUser(HttpUser):
    wait_time = lambda self: 0  # noqa: E731 -- back-to-back requests

    @task
    def work(self):
        self.client.get("/work", name="/work")


class FourStageShape(LoadTestShape):
    def tick(self):
        run_time = self.get_run_time()
        stage = int(run_time // _STAGE_SECONDS)
        if stage >= len(_STAGES):
            return None
        users = _STAGES[stage]
        return users, users  # (user_count, spawn_rate)
