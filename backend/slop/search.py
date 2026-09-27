"""Evidence-level hybrid retrieval, with deterministic lexical fallback."""

import os
import re
from functools import lru_cache

from sqlalchemy import delete, select

from slop.db import CourseVersion, Evidence

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


def search(data, query, year, compatible_first=True, limit=20, session=None):
    query_tokens = tokens(query)
    expanded = query + " " + " ".join(ALIASES[t] for t in query_tokens if t in ALIASES)
    words = tokens(expanded)
    courses = {c["code"]: c for c in data["courses"] if c["year"] == year}
    degree = next((d for d in data["degrees"] if d["year"] == year), None)
    degree_codes = set(degree["course_references"]) if degree else set()
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
        fit = (
            "REQUIRED"
            if code in degree_codes
            else "ELECTIVE_CANDIDATE"
            if c["elective"] is True
            else "UNKNOWN"
            if c["elective"] is None
            else "OUTSIDE_DEGREE"
        )
        result = grouped.setdefault(
            code, {"course": c, "score": score, "degree_fit": fit, "evidence": []}
        )
        if len(result["evidence"]) < 3:
            result["evidence"].append({"field": field, "text": text})
    results = sorted(
        grouped.values(),
        key=lambda r: (
            0
            if not compatible_first or r["degree_fit"] in {"REQUIRED", "ELECTIVE_CANDIDATE"}
            else 1,
            -r["score"],
        ),
    )
    return {"mode": mode, "model": MODEL if mode == "HYBRID" else None, "results": results[:limit]}


def route(query):
    q = query.lower()
    code = re.search(r"\b[A-Z]{3,8}\s?\d{4}[A-Z]?\b", query.upper())
    if re.search(r"\b(generate|build|finish)\b.*\b(plan|degree)\b", q):
        intent = "PLAN_GENERATE"
    elif re.search(r"\b(validate|check|remaining|requirements)\b", q):
        intent = "PLAN_VALIDATE"
    elif code and re.search(r"\b(prerequisite|blocked|path|can i take|need before)\b", q):
        intent = "PREREQUISITE_PATH"
    elif re.search(r"\b(degree|bachelor|major)\b", q) and not re.search(
        r"\b(elective|course)\b", q
    ):
        intent = "DEGREE_SEARCH"
    else:
        intent = "COURSE_SEARCH"
    return {"intent": intent, "course": code[0].replace(" ", "") if code else None}
