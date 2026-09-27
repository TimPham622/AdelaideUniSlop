"""Evidence-level hybrid retrieval, with deterministic lexical fallback."""

import os
import re
from functools import lru_cache

from sqlalchemy import delete, distinct, func, select

from slop.course_codes import SOURCE_CODE_FRAGMENT
from slop.db import CourseVersion, Evidence
from slop.planner import requirement_fit

MODEL = "BAAI/bge-small-en-v1.5"
ALIASES = {
    "cad": "computer aided design 3d modelling solid modelling engineering drawing",
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "hci": "human computer interaction",
}


@lru_cache(maxsize=1)
def encoder():
    from fastembed import TextEmbedding

    return TextEmbedding(
        model_name=MODEL, cache_dir=os.environ.get("EMBEDDING_CACHE", ".cache/models"), threads=2
    )


def chunks(course):
    yield "title", f"{course['code']} {course['title']}"
    if course["overview"]:
        yield "overview", course["overview"]
    for outcome in course["outcomes"]:
        yield "learning_outcome", outcome
    for assessment in course["assessments"]:
        yield "assessment", assessment


def embed_catalogue(session):
    records = []
    for version in session.scalars(select(CourseVersion)):
        expected = []
        for index, (field, text) in enumerate(chunks(version.data)):
            key = f"{version.id}:{index}"
            expected.append(key)
            old = session.get(Evidence, key)
            if not old or old.text != text or old.model != MODEL or old.vector is None:
                records.append((key, version.id, field, text))
        session.execute(
            delete(Evidence).where(Evidence.version_id == version.id, Evidence.id.not_in(expected))
        )
    if records:
        vectors = encoder().embed([r[3] for r in records], batch_size=32)
        for record, vector in zip(records, vectors, strict=True):
            key, vid, field, text = record
            session.merge(
                Evidence(
                    id=key,
                    version_id=vid,
                    field=field,
                    text=text,
                    model=MODEL,
                    vector=vector.tolist(),
                )
            )
    session.commit()
    return len(records)


def tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def search(data, query, year, compatible_first=True, limit=20, session=None,
           degree="bcomp", option="general"):
    query_tokens = tokens(query)
    expanded = query + " " + " ".join(ALIASES[t] for t in query_tokens if t in ALIASES)
    words = tokens(expanded)
    courses = {c["code"]: c for c in data["courses"] if c["year"] == year}
    evidence, lexical, semantic = {}, [], []
    for code, c in courses.items():
        for i, (field, text) in enumerate(chunks(c)):
            key = f"{year}:{code}:{i}"
            evidence[key] = (code, field, text)
            score = len(words & tokens(text)) / max(1, len(words))
            if re.sub(r"\s", "", query).upper() == code:
                score += 10
            if score > 0:
                lexical.append((key, score))
    lexical.sort(key=lambda x: -x[1])
    mode = "LEXICAL"
    if session is not None and os.environ.get("SEMANTIC_SEARCH", "1") == "1":
        exists = session.scalar(
            select(Evidence.id).where(Evidence.version_id.like(f"{year}:%")).limit(1)
        )
        if exists:
            vector = next(iter(encoder().query_embed(query))).tolist()
            distance = Evidence.vector.cosine_distance(vector)
            rows = session.execute(
                select(Evidence.id, distance.label("distance"))
                .where(Evidence.version_id.like(f"{year}:%"), Evidence.model == MODEL)
                .order_by(distance)
                .limit(100)
            )
            semantic = [
                (r.id, 1 - r.distance) for r in rows if r.distance < 0.65 and r.id in evidence
            ]
            mode = "HYBRID"
    scores = {}
    for ranking in [lexical, semantic]:
        for rank, (key, _) in enumerate(ranking):
            scores[key] = scores.get(key, 0) + 1 / (60 + rank + 1)
    grouped = {}
    for key, score in sorted(scores.items(), key=lambda x: -x[1]):
        code, field, text = evidence[key]
        c = courses[code]
        fit = requirement_fit(data, year, degree, option, code)
        result = grouped.setdefault(
            code, {"course": c, "score": score, "requirement_fit": fit,
                   "takeability": "NOT_EVALUATED", "evidence": []}
        )
        if len(result["evidence"]) < 3:
            result["evidence"].append({"field": field, "text": text})
    results = sorted(
        grouped.values(),
        key=lambda r: (
            0 if r["course"]["code"] == re.sub(r"\s", "", query).upper() else 1,
            0
            if not compatible_first or r["requirement_fit"] in {"REQUIRED", "COUNTS_AS_ELECTIVE"}
            else 1,
            -r["score"],
        ),
    )
    indexed = (
        session.scalar(select(func.count(distinct(Evidence.version_id))).where(
            Evidence.version_id.like(f"{year}:%"), Evidence.vector.is_not(None),
            Evidence.model == MODEL))
        if session is not None else 0
    )
    return {"mode": mode, "model": MODEL if mode == "HYBRID" else None,
            "coverage": {"indexed_courses": indexed or 0,
                         "catalogue_courses": len(courses), "source_year": year,
                         "embedding_model": MODEL if mode == "HYBRID" else None,
                         "scope": "Currently ingested course corpus; university-wide completeness is unverified"},
            "results": results[:limit]}


def route(query):
    q = query.lower()
    code = re.search(rf"\b{SOURCE_CODE_FRAGMENT}\b", query.upper())
    if re.search(r"\b(generate|build|finish)\b.*\b(plan|degree)\b", q):
        intent = "PLAN_GENERATE"
    elif re.search(r"\b(validate|check|remaining|requirements)\b", q):
        intent = "PLAN_VALIDATE"
    elif code and re.search(r"\bcan i take\b", q):
        intent = "CAN_TAKE"
    elif code and re.search(r"\b(prerequisite|blocked|path|need before)\b", q):
        intent = "PREREQUISITE_PATH"
    elif re.search(r"\b(degree|bachelor|major)\b", q) and not re.search(
        r"\b(elective|course)\b", q
    ):
        intent = "DEGREE_SEARCH"
    else:
        intent = "COURSE_SEARCH"
    return {"intent": intent, "course": code[0].replace(" ", "") if code else None}
