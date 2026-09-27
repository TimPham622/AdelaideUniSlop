import json
from pathlib import Path

from slop.upstream import UpstreamCourse


def test_raw_upstream_orm_export_retains_uncertainty():
    row = json.loads(Path("data/fixtures/upstream/statx100.raw.json").read_text())
    course = UpstreamCourse.model_validate(row).normalized()
    assert course["code"] == "STATX100"
    assert course["level"] == 1 and course["level_source"] == "UPSTREAM_FIELD"
    assert course["raw"]["prerequisite"] == row["prerequisites"]
    assert course["rules"]["prerequisite"]["type"] == "UNKNOWN"
    assert course["offerings"][0]["key"] == "2026-semester-1"
    assert course["verification"] == "UNKNOWN"


def test_missing_upstream_requisite_cannot_certify_no_requirement():
    row = json.loads(Path("data/fixtures/upstream/statx100.raw.json").read_text())
    row.pop("prerequisites")
    row["terms"] = ["Semester 1", "Semester 2"]
    normalized = UpstreamCourse.model_validate(row).normalized()
    assert normalized["rules"]["prerequisite"]["type"] == "UNKNOWN"
    assert len(normalized["offerings"]) == 2
