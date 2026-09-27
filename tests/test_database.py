"""Real PostgreSQL/pgvector contract tests in an isolated disposable schema."""

import copy
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.parse import quote

import numpy as np
import pytest
from slop.db import (
    Base,
    CourseVersion,
    DegreeVersion,
    Evidence,
    Revision,
    Source,
    catalogue,
    import_catalogue,
)
from slop.search import MODEL, search
from sqlalchemy import create_engine, func, inspect, select, text
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


def test_publication_retires_stale_courses_and_keeps_revision(dbsession):
    payload = json.loads(Path("data/fixtures/catalogue.json").read_text())
    first = import_catalogue(payload, dbsession)
    removed = payload["courses"][0]
    changed = copy.deepcopy(payload)
    changed["courses"] = [c for c in changed["courses"]
                          if (c["year"], c["code"]) != (removed["year"], removed["code"])]
    import_catalogue(changed, dbsession)
    assert not any(c["year"] == removed["year"] and c["code"] == removed["code"]
                   for c in catalogue(dbsession)["courses"])
    assert dbsession.get(Revision, first) is not None
    assert import_catalogue(payload, dbsession) == first
    assert any(c["year"] == removed["year"] and c["code"] == removed["code"]
               for c in catalogue(dbsession)["courses"])


def test_two_degrees_share_catalogue_year(dbsession):
    payload = json.loads(Path("data/fixtures/catalogue.json").read_text())
    other = copy.deepcopy(payload["degrees"][0])
    other["id"] = "another-programme"
    other["program_code"] = "ANOTHER"
    payload["degrees"].append(other)
    import_catalogue(payload, dbsession)
    assert dbsession.scalar(select(func.count()).select_from(DegreeVersion).where(
        DegreeVersion.year == other["year"])) == 2


def test_vector_search_returns_evidence_without_model_network(dbsession, monkeypatch):
    payload = json.loads(Path("data/fixtures/catalogue.json").read_text())
    import_catalogue(payload, dbsession)
    course = next(c for c in payload["courses"] if c["year"] == 2026 and c["code"] == "COMP1002")
    vector = [1.0] + [0.0] * 383
    dbsession.add(
        Evidence(
            id="2026:COMP1002:1",
            version_id="2026:COMP1002",
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
    result = search(payload, "Problem Solving", 2026, True, 50, dbsession)
    assert result["mode"] == "HYBRID"
    match = next(r for r in result["results"] if r["course"]["code"] == "COMP1002")
    assert any(e["text"] == course["overview"] for e in match["evidence"])


def test_empty_schema_migrates_to_explicit_head():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run PostgreSQL migration test")
    schema = "migration_" + uuid.uuid4().hex
    base = create_engine(url)
    with base.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA {schema}"))
    isolated_url = url + ("&" if "?" in url else "?") + "options=" + quote(
        f"-csearch_path={schema},public", safe=""
    )
    try:
        subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       check=True, env={**os.environ, "DATABASE_URL": isolated_url},
                       capture_output=True, text=True)
        inspector = inspect(create_engine(isolated_url))
        assert "degree_identity" in inspector.get_table_names()
        constraints = inspector.get_unique_constraints("degree_version")
        assert any(set(c["column_names"]) == {"degree_id", "year"} for c in constraints)
        assert not any(c["column_names"] == ["year"] for c in constraints)
        vector = next(c for c in inspector.get_columns("search_evidence") if c["name"] == "vector")
        assert "384" in str(vector["type"])
    finally:
        with base.begin() as connection:
            connection.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        base.dispose()
