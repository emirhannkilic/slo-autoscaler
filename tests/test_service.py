from fastapi.testclient import TestClient

from service.app import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_work_rejects_excessive_rounds():
    assert client.get("/work?rounds=50001").status_code == 422


def test_work_rejects_tiny_rounds():
    assert client.get("/work?rounds=99").status_code == 422


def test_work_returns_digest_and_elapsed_time():
    body = client.get("/work?rounds=100").json()
    assert len(body["digest"]) == 64
    assert body["elapsed_ms"] >= 0


def test_work_is_deterministic():
    first = client.get("/work?rounds=200").json()["digest"]
    second = client.get("/work?rounds=200").json()["digest"]
    assert first == second
