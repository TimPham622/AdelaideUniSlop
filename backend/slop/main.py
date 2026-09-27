from __future__ import annotations

import logging
import os
import time
import traceback
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from slop.db import DegreeVersion, catalogue, digest, engine
from slop.planner import can_take, requirement_fit, solve, validate
from slop.schemas import CanTakeRequest, PathRequest, Plan, SearchRequest
from slop.search import route, search

app = FastAPI(title="adelaide uni slop", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost:8080"
    ).split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
windows = defaultdict(deque)
window_lock = Lock()


@app.middleware("http")
async def protection(request: Request, call_next):
    request_id = uuid.uuid4().hex
    if request.url.path.startswith("/api/"):
        now = time.monotonic()
        key = (
            request.client.host if request.client else "unknown",
            "expensive"
            if request.url.path in {"/api/search", "/api/plan/generate", "/api/plan/path",
                                    "/api/plan/can-take", "/api/v1/search",
                                    "/api/v1/plan/generate", "/api/v1/plan/path",
                                    "/api/v1/plan/can-take"}
            else "regular",
        )
        limit = 30 if key[1] == "expensive" else 180
        with window_lock:
            for old in list(windows):
                if not windows[old] or windows[old][-1] < now - 60:
                    del windows[old]
            window = windows[key]
            while window and window[0] < now - 60:
                window.popleft()
            limited = len(window) >= limit
            if not limited:
                window.append(now)
        if limited:
            return JSONResponse(
                {"detail": "Rate limit reached; retry in a minute"},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        if request.method == "POST":
            length = 0
            chunks = []
            async for chunk in request.stream():
                length += len(chunk)
                if length > 262144:
                    return JSONResponse({"detail": "Request exceeds 256 KiB"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001 - redact all uncaught request errors
        logging.getLogger("slop").error(
            "request_id=%s exception=%s frames=%s",
            request_id,
            type(exc).__name__,
            [(f.name, f.lineno) for f in traceback.extract_tb(exc.__traceback__)],
        )
        # No request bodies, URLs, search queries or student information in error output.
        response = JSONResponse(
            {"detail": "Request failed", "request_id": request_id}, status_code=500
        )
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def invalid_value(request, exc):
    return JSONResponse({"detail": str(exc)}, status_code=422)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    try:
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
            if not session.scalar(select(DegreeVersion.id).limit(1)):
                raise HTTPException(503, "Catalogue not loaded")
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 - readiness must not expose connection details
        raise HTTPException(503, "Database unavailable") from None
    return {"status": "ready"}


@app.get("/api/catalogue")
@app.get("/api/v1/catalogue")
def get_catalogue(request: Request):
    with Session(engine) as session:
        data = catalogue(session)
    revision = digest(data)
    return JSONResponse({**data, "revision": revision})


@app.get("/api/requirement-fit")
@app.get("/api/v1/requirement-fit")
def get_requirement_fit(year: int, degree: str = "bcomp", option: str = "general"):
    with Session(engine) as session:
        data = catalogue(session)
    return {c["code"]: requirement_fit(data, year, degree, option, c["code"])
            for c in data["courses"] if c["year"] == year}


@app.post("/api/plan/validate")
@app.post("/api/v1/plan/validate")
def validate_plan(plan: Plan):
    with Session(engine) as session:
        return validate(plan, catalogue(session))


@app.post("/api/plan/generate")
@app.post("/api/v1/plan/generate")
def generate_plan(plan: Plan):
    with Session(engine) as session:
        data = catalogue(session)
    return solve(plan, data)


@app.post("/api/plan/path")
@app.post("/api/v1/plan/path")
def prerequisite_path(request: PathRequest):
    with Session(engine) as session:
        data = catalogue(session)
    return solve(request.plan, data, target=request.target, start=request.start)


@app.post("/api/plan/can-take")
@app.post("/api/v1/plan/can-take")
def check_takeability(request: CanTakeRequest):
    with Session(engine) as session:
        data = catalogue(session)
    return can_take(request.plan, data, request.target, request.period)


@app.post("/api/search")
@app.post("/api/v1/search")
def search_courses(request: SearchRequest):
    with Session(engine) as session:
        return search(
            catalogue(session),
            request.query,
            request.year,
            request.compatible_first,
            request.limit,
            session,
            request.degree,
            request.option,
        )


@app.post("/api/route")
@app.post("/api/v1/route")
def route_query(request: SearchRequest):
    return route(request.query)


@app.get("/api/privacy")
@app.get("/api/v1/privacy")
def privacy():
    return {
        "plans": "Stored only in your browser. Validation and generation send transient plan contents to this server.",
        "search": "Queries are processed transiently. No accounts, analytics or query logs.",
        "limits": "Short-lived in-memory IP rate limits expire after one minute.",
        "ai": "Generative AI is disabled. Local embeddings power semantic retrieval.",
    }


@app.get("/api/v1/degrees")
def list_degrees(year: int | None = None, q: str = ""):
    if len(q) > 200:
        raise HTTPException(422, "Search query is too long")
    with Session(engine) as session:
        degrees = catalogue(session)["degrees"]
    needle = q.casefold().strip()
    rows = [d for d in degrees if (year is None or d["year"] == year)
            and (not needle or needle in d.get("title", "").casefold()
                 or needle in d.get("id", "").casefold()
                 or needle in d.get("program_code", "").casefold())]
    return {"results": sorted(rows, key=lambda d: (d.get("title", d["id"]), d["year"])),
            "count": len(rows)}


@app.get("/api/v1/degrees/{degree_id}")
def get_degree(degree_id: str, year: int | None = None):
    with Session(engine) as session:
        versions = [d for d in catalogue(session)["degrees"] if d["id"] == degree_id
                    and (year is None or d["year"] == year)]
    if not versions:
        raise HTTPException(404, "Degree version not found")
    return max(versions, key=lambda d: d["year"])


@app.get("/api/v1/courses")
def list_courses(year: int | None = None, q: str = "", limit: int = 50, offset: int = 0):
    if len(q) > 200 or not 1 <= limit <= 100 or offset < 0:
        raise HTTPException(422, "Invalid catalogue query")
    with Session(engine) as session:
        courses = catalogue(session)["courses"]
    needle = q.casefold().strip()
    rows = [c for c in courses if (year is None or c["year"] == year)
            and (not needle or needle in c["code"].casefold()
                 or needle in c["title"].casefold())]
    rows.sort(key=lambda c: (c["code"], c["year"]))
    return {"results": rows[offset:offset + limit], "count": len(rows)}


@app.get("/api/v1/courses/{code}/versions")
def course_versions(code: str):
    with Session(engine) as session:
        versions = [c for c in catalogue(session)["courses"] if c["code"] == code.upper()]
    if not versions:
        raise HTTPException(404, "Course not found")
    return {"results": sorted(versions, key=lambda c: c["year"])}


@app.get("/api/v1/courses/{code}")
def get_course(code: str, year: int | None = None):
    with Session(engine) as session:
        versions = [c for c in catalogue(session)["courses"] if c["code"] == code.upper()
                    and (year is None or c["year"] == year)]
    if not versions:
        raise HTTPException(404, "Course version not found")
    return max(versions, key=lambda c: c["year"])
