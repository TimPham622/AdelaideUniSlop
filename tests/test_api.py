import pytest
from fastapi.testclient import TestClient
from slop import main
from slop.main import app, windows


@pytest.fixture
def client(small_catalogue, monkeypatch):
    windows.clear()
    monkeypatch.setattr(main, "catalogue", lambda session: small_catalogue)
    monkeypatch.setenv("SEMANTIC_SEARCH", "0")
    return TestClient(app)


def test_api_validation_path_search_and_router(client):
    plan = {"year": 2026}
    assert client.post("/api/plan/validate", json=plan).json()["status"] == "INVALID"
    response = client.post("/api/plan/path", json={"plan": plan, "target": "COMP2001"})
    assert response.status_code == 200
    assert response.json()["status"] == "VALID"
    assert (
        client.post("/api/search", json={"query": "COMP1001", "year": 2026}).json()["results"][0][
            "course"
        ]["code"]
        == "COMP1001"
    )
    for q, intent in [
        ("can I take COMP1001", "PREREQUISITE_PATH"),
        ("build my degree plan", "PLAN_GENERATE"),
        ("check my plan", "PLAN_VALIDATE"),
        ("computer science degree", "DEGREE_SEARCH"),
        ("CAD", "COURSE_SEARCH"),
    ]:
        assert client.post("/api/route", json={"query": q, "year": 2026}).json()["intent"] == intent


def test_strict_input_rejection(client):
    assert (
        client.post("/api/plan/validate", json={"year": 2026, "arbitrary": "payload"}).status_code
        == 422
    )
    assert client.post("/api/plan/validate", json={"year": 2026, "max_units": 0}).status_code == 422
    assert client.post("/api/search", json={"query": "x" * 401, "year": 2026}).status_code == 422
    assert (
        client.post(
            "/api/plan/validate",
            content=b"x" * 262145,
            headers={"Content-Type": "application/json"},
        ).status_code
        == 413
    )


def test_rate_limit_and_privacy_headers(client):
    for _ in range(30):
        assert client.post("/api/search", json={"query": "CAD", "year": 2026}).status_code == 200
    r = client.post("/api/search", json={"query": "CAD", "year": 2026})
    assert r.status_code == 429 and r.headers["retry-after"] == "60"
    r = client.get("/health")
    assert r.headers["cache-control"] == "no-store"
    assert "request_id" not in r.json()
