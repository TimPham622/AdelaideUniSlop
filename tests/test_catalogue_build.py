import copy
import json
from pathlib import Path

import pytest
from slop.catalogue_build import course_quality, merge_upstream_courses


def test_upstream_merge_keeps_reviewed_versions_and_adds_new_unverified(small_catalogue):
    raw = json.loads(Path("data/fixtures/upstream/statx100.raw.json").read_text())
    original = copy.deepcopy(small_catalogue)
    merged, summary = merge_upstream_courses(small_catalogue | {"schema_version": 1}, [raw])
    assert summary["added_unverified_versions"] == 1
    imported = next(course for course in merged["courses"] if course["code"] == "STATX100")
    assert imported["verification"] == "UNKNOWN"
    assert small_catalogue == original
    repeated, summary = merge_upstream_courses(merged, [raw])
    assert summary["preserved_existing_versions"] == 1
    assert repeated == merged


def test_upstream_merge_rejects_duplicates_and_orphan_year(small_catalogue):
    raw = json.loads(Path("data/fixtures/upstream/statx100.raw.json").read_text())
    base = small_catalogue | {"schema_version": 1}
    with pytest.raises(ValueError, match="Duplicate"):
        merge_upstream_courses(base, [raw, raw])
    with pytest.raises(ValueError, match="No degree catalogue"):
        merge_upstream_courses(base, [{**raw, "year": 2028}])


def test_course_quality_does_not_count_missing_rules_as_parsed():
    report = course_quality([{"code": "TEST1001", "raw": {}, "rules": {}}])
    assert report["with_parsed_prerequisites"] == {"count": 0, "percent": 0.0}
