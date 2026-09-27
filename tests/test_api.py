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
        ("can I take COMP1001", "CAN_TAKE"),
        ("fastest path to COMP1001", "PREREQUISITE_PATH"),
        ("build my degree plan", "PLAN_GENERATE"),
        ("check my plan", "PLAN_VALIDATE"),
        ("computer science degree", "DEGREE_SEARCH"),
        ("CAD", "COURSE_SEARCH"),
    ]:
        assert client.post("/api/route", json={"query": q, "year": 2026}).json()["intent"] == intent


def test_period_takeability_and_requirement_fit_are_separate(client):
    response = client.post("/api/plan/can-take", json={
        "plan": {"year": 2026}, "target": "COMP1002", "period": "2026-semester-2"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    assert any(reason["kind"] == "prerequisite" for reason in response.json()["reasons"])
    result = client.post("/api/search", json={"query": "COMP1002", "year": 2026}).json()["results"][0]
    assert result["requirement_fit"] == "REQUIRED"
    assert result["takeability"] == "NOT_EVALUATED"


def test_exact_course_code_is_not_hidden_by_fit_first_limit(client, small_catalogue):
    course = next(c for c in small_catalogue["courses"]
                  if c["year"] == 2026 and c["code"] == "COMP2002")
    course["elective"] = False
    result = client.post("/api/search", json={
        "query": "COMP2002", "year": 2026, "compatible_first": True, "limit": 1
    }).json()["results"][0]
    assert result["course"]["code"] == "COMP2002"
    assert result["requirement_fit"] == "OUTSIDE_KNOWN_RULES"


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


def test_versioned_degree_and_course_catalogue(client, small_catalogue):
    alternate = {**small_catalogue["degrees"][0], "id": "other-degree",
                 "title": "Another degree", "program_code": "OTHER"}
    small_catalogue["degrees"].append(alternate)
    listed = client.get("/api/v1/degrees", params={"year": 2026}).json()
    assert {item["id"] for item in listed["results"]} == {"bcomp", "other-degree"}
    assert client.get("/api/v1/degrees/other-degree", params={"year": 2026}).json()["id"] == "other-degree"
    assert client.get("/api/v1/degrees/missing").status_code == 404
    assert client.get("/api/v1/courses/COMP1001").json()["year"] == 2027
    assert len(client.get("/api/v1/courses/COMP1001/versions").json()["results"]) == 2
    assert client.get("/api/v1/courses", params={"year": 2026, "q": "COMP1001"}).json()["count"] == 1
    plan = {"schema_version": 2, "id": "new", "name": "Alternate", "catalogue_year": 2026,
            "degree_id": "other-degree", "option_ids": [], "audience": "domestic"}
    response = client.post("/api/v1/plan/validate", json=plan)
    assert response.status_code == 200
    assert response.json()["status"] == "INVALID"
