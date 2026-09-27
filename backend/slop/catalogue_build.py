"""Merge a reviewed catalogue with raw upstream course rows into a draft."""

from __future__ import annotations

import copy

from slop.upstream import UpstreamCourse


def merge_upstream_courses(base: dict, rows: list[dict]) -> tuple[dict, dict]:
    if base.get("schema_version") != 1 or not isinstance(base.get("degrees"), list):
        raise ValueError("Expected a version-one catalogue")
    if not isinstance(base.get("courses"), list):
        raise TypeError("Catalogue courses are missing")
    allowed_years = {degree["year"] for degree in base["degrees"]}
    result = copy.deepcopy(base)
    existing = {(course["year"], course["code"]) for course in result["courses"]}
    seen = set()
    added = 0
    preserved = 0
    for row in rows:
        course = UpstreamCourse.model_validate(row).normalized()
        key = (course["year"], course["code"])
        if key in seen:
            raise ValueError(f"Duplicate upstream course version: {key}")
        seen.add(key)
        if course["year"] not in allowed_years:
            raise ValueError(f"No degree catalogue for upstream year {course['year']}")
        if key in existing:
            preserved += 1
            continue
        result["courses"].append(course)
        existing.add(key)
        added += 1
    result["courses"].sort(key=lambda course: (course["year"], course["code"]))
    return result, {"added_unverified_versions": added,
                    "preserved_existing_versions": preserved,
                    "course_versions": len(result["courses"])}


def course_quality(courses: list[dict]) -> dict:
    total = len(courses)
    checks = {
        "with_title": lambda c: bool(c.get("title")),
        "with_units": lambda c: c.get("units") is not None,
        "with_level": lambda c: c.get("level") is not None,
        "with_overview": lambda c: bool(c.get("overview")),
        "with_outcomes": lambda c: bool(c.get("outcomes")),
        "with_assessments": lambda c: bool(c.get("assessments")),
        "with_raw_prerequisites": lambda c: bool(c.get("raw", {}).get("prerequisite")),
        "with_parsed_prerequisites": lambda c: c.get("rules", {}).get("prerequisite", {}).get("type")
        in {"ALL", "ANY", "COURSE", "MIN_UNITS", "EXACT_UNITS", "MAX_UNITS", "NOT"},
        "with_source_year_match": lambda c: c.get("year_status") == "MATCH",
        "with_offerings": lambda c: bool(c.get("offerings")),
        "university_wide_electives": lambda c: c.get("elective") is True,
    }
    counts = {key: sum(bool(test(c)) for c in courses) for key, test in checks.items()}
    return {"total": total, **{key: {"count": count,
                                    "percent": round(100 * count / total, 1) if total else 0}
                               for key, count in counts.items()}}
