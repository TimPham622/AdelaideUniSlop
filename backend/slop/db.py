from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
    delete,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg://slop:slop@localhost:5432/slop")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
Json = JSON().with_variant(JSONB, "postgresql")


class Base(DeclarativeBase):
    pass


class Revision(Base):
    __tablename__ = "catalogue_revision"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict] = mapped_column(Json)


class Source(Base):
    __tablename__ = "source_document"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    year: Mapped[int] = mapped_column(Integer)
    provenance: Mapped[dict] = mapped_column(Json)


class CourseIdentity(Base):
    __tablename__ = "course_identity"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    institutional_id: Mapped[str] = mapped_column(String(80))


class CourseVersion(Base):
    __tablename__ = "course_version"
    __table_args__ = (UniqueConstraint("code", "year"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    code: Mapped[str] = mapped_column(ForeignKey("course_identity.code"))
    year: Mapped[int] = mapped_column(Integer, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_document.id"))
    data: Mapped[dict] = mapped_column(Json)


class DegreeIdentity(Base):
    __tablename__ = "degree_identity"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    program_code: Mapped[str] = mapped_column(String(80))
    canonical_slug: Mapped[str] = mapped_column(String(160))


class DegreeVersion(Base):
    __tablename__ = "degree_version"
    __table_args__ = (UniqueConstraint("degree_id", "year"),)
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    degree_id: Mapped[str] = mapped_column(ForeignKey("degree_identity.id"))
    year: Mapped[int] = mapped_column(Integer, index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("source_document.id"))
    data: Mapped[dict] = mapped_column(Json)


class Offering(Base):
    __tablename__ = "course_offering"
    id: Mapped[str] = mapped_column(String(160), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("course_version.id"))
    period: Mapped[str] = mapped_column(String(80), index=True)
    data: Mapped[dict] = mapped_column(Json)


class Relationship(Base):
    __tablename__ = "course_relationship"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    data: Mapped[dict] = mapped_column(Json)


class Evidence(Base):
    __tablename__ = "search_evidence"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("course_version.id"), index=True)
    field: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String(100))
    vector: Mapped[list | None] = mapped_column(
        Vector(384).with_variant(JSON(), "sqlite"), nullable=True
    )


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def import_catalogue(payload, session: Session):
    """Idempotent, transactional publication of a reviewed Git snapshot."""
    from slop.rules import Rule

    revision = digest(payload)
    existing_revision = session.get(Revision, revision)
    if existing_revision and digest(catalogue(session)) == digest(payload):
        return revision
    for data in payload["courses"] + payload["degrees"]:
        source = data["source"]
        sid = digest(source)
        session.merge(Source(id=sid, year=data["year"], provenance=source))
    session.flush()
    for d in payload["degrees"]:
        session.merge(DegreeIdentity(
            id=d["id"], program_code=d.get("program_code", d["id"].upper()),
            canonical_slug=d["id"]
        ))
    for c in payload["courses"]:
        for rule in c["rules"].values():
            Rule.model_validate(rule)
        session.merge(CourseIdentity(code=c["code"], institutional_id=c["identity"]))
    session.flush()
    published_years = {d["year"] for d in payload["degrees"]}
    incoming_versions = {f"{c['year']}:{c['code']}" for c in payload["courses"]}
    incoming_degrees = {f"{d['year']}:{d['id']}" for d in payload["degrees"]}
    stale_versions = [v.id for v in session.scalars(select(CourseVersion))
                      if v.year in published_years and v.id not in incoming_versions]
    if stale_versions:
        session.execute(delete(Evidence).where(Evidence.version_id.in_(stale_versions)))
        session.execute(delete(Offering).where(Offering.version_id.in_(stale_versions)))
        session.execute(delete(CourseVersion).where(CourseVersion.id.in_(stale_versions)))
    stale_degrees = [d.id for d in session.scalars(select(DegreeVersion))
                     if d.year in published_years and d.id not in incoming_degrees]
    if stale_degrees:
        session.execute(delete(DegreeVersion).where(DegreeVersion.id.in_(stale_degrees)))
    for c in payload["courses"]:
        vid = f"{c['year']}:{c['code']}"
        old = session.get(CourseVersion, vid)
        if old and old.data != c:
            session.execute(delete(Evidence).where(Evidence.version_id == vid))
        session.merge(
            CourseVersion(
                id=vid, year=c["year"], code=c["code"], source_id=digest(c["source"]), data=c
            )
        )
    for d in payload["degrees"]:
        session.merge(
            DegreeVersion(
                id=f"{d['year']}:{d['id']}", degree_id=d["id"], year=d["year"],
                source_id=digest(d["source"]), data=d
            )
        )
    session.flush()
    for c in payload["courses"]:
        vid = f"{c['year']}:{c['code']}"
        for old in session.scalars(select(Offering).where(Offering.version_id == vid)):
            session.delete(old)
        session.flush()
        for o in c["offerings"]:
            session.add(Offering(id=f"{vid}:{o['key']}", version_id=vid, period=o["key"], data=o))
    for old in session.scalars(select(Relationship)):
        if old.data.get("year") in published_years:
            session.delete(old)
    session.flush()
    for rel in payload.get("relationships", []):
        if rel["type"] not in {
            "EQUIVALENT_TO",
            "SUPERSEDES",
            "APPROVED_SUBSTITUTE_FOR",
            "INCOMPATIBLE_WITH",
        } or not rel.get("source"):
            raise ValueError("Relationship must have a supported type and provenance")
        session.merge(Relationship(id=digest(rel), data=rel))
    if not existing_revision:
        session.add(Revision(id=revision, payload=payload))
    session.commit()
    return revision


def catalogue(session: Session):
    return {
        "schema_version": 1,
        "degrees": [
            d.data for d in session.scalars(select(DegreeVersion).order_by(DegreeVersion.year))
        ],
        "courses": [
            c.data for c in session.scalars(select(CourseVersion).order_by(CourseVersion.id))
        ],
        "relationships": [r.data for r in session.scalars(select(Relationship))],
    }


def apply_overrides(payload, directory=Path("data/rule_overrides")):
    for file in sorted(Path(directory).rglob("*.json")):
        override = json.loads(file.read_text())
        if not all(
            override.get(k)
            for k in ["author", "reviewed_at", "source_hash", "source_url", "reason", "rule"]
        ):
            raise ValueError(f"Incomplete override provenance: {file}")
        from slop.rules import Rule

        rule = Rule.model_validate(override["rule"]).model_dump()
        matches = [
            c
            for c in payload["courses"]
            if c["year"] == override["year"] and c["code"] == override["course"]
        ]
        if len(matches) != 1:
            raise ValueError(f"Override has no unique target: {file}")
        course = matches[0]
        kind = override["kind"]
        if kind not in course["rules"]:
            raise ValueError("Unknown requisite kind")
        if course["source"]["sha256"] != override["source_hash"]:
            course["rules"][kind] = Rule(
                type="UNKNOWN",
                raw=course["raw"].get(kind) or "",
                warning="Override source changed; maintainer review required",
            ).model_dump()
        else:
            course["rules"][kind] = rule
        course.setdefault("overrides", []).append(override)
    return payload
