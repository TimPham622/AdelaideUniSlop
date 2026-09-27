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
        major = next(g for g in parsed["groups"] if g["id"] == "major-courses")
        assert major["rule"]["type"] == "ALL"
        assert "STATX100" in major["codes"]
        assert major["units"] == 54


def test_degree_mismatched_year_downgrades_source_verification():
    stem = "degree-2026-artificial-intelligence-and-machine-learning"
    source = json.loads((ROOT / f"{stem}.source.json").read_text())
    source["year"] = 2027
    parsed = parse_degree((ROOT / f"{stem}.html").read_text(), source)
    assert parsed["year_status"] == "MISMATCH"
    assert parsed["page_year"] == 2026
    assert parsed["verification"] != "VERIFIED"


def test_official_course_excerpts_preserve_level_and_requisite_logic():
    def parsed(name, code):
        stem = f"course-{name}-excerpt"
        source = json.loads((ROOT / f"{stem}.source.json").read_text())
        return parse_course((ROOT / f"{stem}.html").read_text(), source, code)

    machine_learning = parsed("comp2052", "COMP2052")
    assert machine_learning["level"] == 2
    assert machine_learning["level_source"] == "OFFICIAL_FIELD"
    assert [child["course"] for child in machine_learning["rules"]["prerequisite"]["children"]] == [
        "COMP1002", "MATH1022", "STATX100"
    ]
    assert machine_learning["rules"]["antirequisite"]["course"] == "ARTI2001"
    assert machine_learning["rules"]["prerequisite"]["raw"] == machine_learning["raw"]["prerequisite"]
    ambiguous = parsed("comp3045", "COMP3045")
    assert ambiguous["rules"]["prerequisite"]["type"] == "UNKNOWN"
    assert ambiguous["rules"]["prerequisite"]["raw"] == ambiguous["raw"]["prerequisite"]
    info = parsed("info1002-2027", "INFO1002")
    assert info["level"] == 2  # Its numeric code starts with 1; the official field says 2.
