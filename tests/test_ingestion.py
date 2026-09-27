import json
from pathlib import Path

import pytest
from slop.db import apply_overrides
from slop.ingestion import Fetcher, parse_course, parse_degree

ROOT = Path("data/fixtures/html")


@pytest.mark.parametrize("year", [2026, 2027])
def test_every_verified_reference_degree_rule_has_golden_fixture(year):
    stem = f"degree-{year}"
    source = json.loads((ROOT / f"{stem}.source.json").read_text())
    parsed = parse_degree((ROOT / f"{stem}.html").read_text(), source)
    expected = json.loads((ROOT / f"{stem}.expected.json").read_text())
    for field, value in expected.items():
        assert parsed[field] == value
    assert len(parsed["groups"]) == 4
    assert len(parsed["standard_plan"]) == 22
    assert all(g["verification"] == "VERIFIED" for g in parsed["groups"])


def test_course_parser_golden_and_missing_fields():
    stem = "course-comp1002-2026"
    source = json.loads((ROOT / f"{stem}.source.json").read_text())
    parsed = parse_course((ROOT / f"{stem}.html").read_text(), source, "COMP1002")
    expected = json.loads((ROOT / f"{stem}.expected.json").read_text())
    for field, value in expected.items():
        assert parsed[field] == value
    missing = parse_course("<h1>Test</h1>", source, "COMP1002")
    assert missing["rules"]["prerequisite"]["type"] == "UNKNOWN"
    assert missing["exam"] == "UNKNOWN"
    assert missing["offerings"] == []


def test_unfamiliar_degree_summary_cannot_disappear():
    source = json.loads((ROOT / "degree-2026.source.json").read_text())
    html = (
        (ROOT / "degree-2026.html")
        .read_text()
        .replace(
            "Complete 144 units comprising:",
            "Complete 144 units including an approved thesis comprising:",
        )
    )
    assert not parse_degree(html, source)["summary_verified"]


def test_crawler_blocks_arbitrary_urls_before_network(tmp_path):
    fetcher = Fetcher(tmp_path)
    for url in [
        "http://adelaide.edu.au/study/a",
        "https://evil.test/study/a",
        "https://adelaide.edu.au/admin",
        "https://adelaide.edu.au@evil.test/study/a",
    ]:
        with pytest.raises(ValueError):
            fetcher.fetch(url, 2026)


def test_changed_source_invalidates_override(tmp_path):
    override = {
        "author": "Maintainer",
        "reviewed_at": "2026-09-27",
        "source_hash": "old",
        "source_url": "https://adelaide.edu.au/study/courses/2026/comp-1002/",
        "reason": "Reviewed official prerequisite",
        "rule": {"type": "ALL"},
        "year": 2026,
        "course": "COMP1002",
        "kind": "prerequisite",
    }
    (tmp_path / "override.json").write_text(json.dumps(override))
    data = {
        "courses": [
            {
                "year": 2026,
                "code": "COMP1002",
                "source": {"sha256": "new"},
                "rules": {"prerequisite": {"type": "ALL"}},
                "raw": {"prerequisite": "new wording"},
            }
        ]
    }
    assert (
        apply_overrides(data, tmp_path)["courses"][0]["rules"]["prerequisite"]["type"] == "UNKNOWN"
    )


@pytest.mark.parametrize(
    "expected_file", sorted(ROOT.glob("degree-*-*.expected.json")), ids=lambda p: p.stem
)
def test_major_requirement_goldens(expected_file):
    stem = expected_file.name.removesuffix(".expected.json")
    source = json.loads((ROOT / f"{stem}.source.json").read_text())
    parsed = parse_degree((ROOT / f"{stem}.html").read_text(), source)
    expected = json.loads(expected_file.read_text())
    for field, value in expected.items():
        assert parsed[field] == value
    if "artificial-intelligence" in stem:
        assert (
            next(g for g in parsed["groups"] if g["id"] == "major-courses")["rule"]["type"]
            == "UNKNOWN"
        )
