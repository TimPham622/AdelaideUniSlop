"""Real PostgreSQL/pgvector contract tests in an isolated disposable schema."""

import copy
import json
import os
import uuid
from pathlib import Path

import numpy as np
import pytest
from slop.db import Base, CourseVersion, Evidence, Source, import_catalogue
from slop.search import MODEL, search
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session


@pytest.fixture
def dbsession():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL integration tests")
    base = create_engine(url)
    schema = "test_" + uuid.uuid4().hex
    with base.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine = base.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        with base.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        base.dispose()


def test_publication_idempotence_reversion_and_provenance(dbsession):
    payload = json.loads(Path("data/fixtures/catalogue.json").read_text())
    first = import_catalogue(payload, dbsession)
    source_count = dbsession.scalar(select(func.count()).select_from(Source))
    assert import_catalogue(payload, dbsession) == first
    assert dbsession.scalar(select(func.count()).select_from(CourseVersion)) == len(
        payload["courses"]
    )
    assert dbsession.scalar(select(func.count()).select_from(Source)) == source_count
    changed = copy.deepcopy(payload)
    changed["courses"][0]["title"] = "Changed catalogue title"
    assert import_catalogue(changed, dbsession) != first
    assert import_catalogue(payload, dbsession) == first
    assert (
        dbsession.get(
            CourseVersion, f"{payload['courses'][0]['year']}:{payload['courses'][0]['code']}"
        ).data["title"]
        == payload["courses"][0]["title"]
    )


def test_vector_search_returns_evidence_without_model_network(dbsession, monkeypatch):
    payload = json.loads(Path("data/fixtures/catalogue.json").read_text())
    import_catalogue(payload, dbsession)
    course = next(c for c in payload["courses"] if c["year"] == 2026 and c["code"] == "ENGM4015")
    vector = [1.0] + [0.0] * 383
    dbsession.add(
        Evidence(
            id="2026:ENGM4015:1",
            version_id="2026:ENGM4015",
            field="overview",
            text=course["overview"],
            model=MODEL,
            vector=vector,
        )
    )
    dbsession.commit()

    class FixedEncoder:
        def query_embed(self, query):
            return iter([np.array(vector)])

    import slop.search as search_module

    monkeypatch.setattr(search_module, "encoder", lambda: FixedEncoder())
    monkeypatch.setenv("SEMANTIC_SEARCH", "1")
    result = search(payload, "CAD", 2026, True, 50, dbsession)
    assert result["mode"] == "HYBRID"
    match = next(r for r in result["results"] if r["course"]["code"] == "ENGM4015")
    assert any(e["text"] == course["overview"] for e in match["evidence"])
