import pytest
from slop.planner import solve, validate
from slop.rules import compile_rule
from slop.schemas import Attempt, Credit, Plan


def item(code, term="2026-semester-1", status="PLANNED", id=None, locked=False):
    return Attempt(id=id or code, course=code, term=term, status=status, locked=locked)


def test_same_period_does_not_satisfy_prerequisite(small_catalogue):
    p = Plan(year=2026, attempts=[item("COMP1001"), item("COMP1002")])
    report = validate(p, small_catalogue)
    second = next(c for c in report["course_checks"] if c["course"] == "COMP1002")
    assert second["status"] == "UNSATISFIED"
    assert any(
        r["kind"] == "prerequisite" and r["evaluation"]["rule"]["course"] == "COMP1001"
        for r in second["reasons"]
    )


@pytest.mark.parametrize("status", ["FAILED", "WITHDRAWN"])
def test_failed_and_withdrawn_do_not_count(small_catalogue, status):
    p = Plan(
        year=2026, attempts=[item("COMP1001", status=status), item("COMP1002", "2026-semester-2")]
    )
    r = validate(p, small_catalogue)
    assert r["earned_units"] == 0
    assert (
        next(c for c in r["course_checks"] if c["course"] == "COMP1002")["status"] == "UNSATISFIED"
    )


def test_repeat_preserves_attempt_and_counts_once(small_catalogue):
    p = Plan(
        year=2026,
        attempts=[
            item("COMP1001", status="COMPLETED"),
            item("COMP1001", status="COMPLETED", id="repeat"),
        ],
    )
    r = validate(p, small_catalogue)
    assert r["earned_units"] == 6
    assert r["course_checks"][1]["status"] == "UNSATISFIED"


def test_waiver_is_conditional_and_grants_no_units(small_catalogue):
    p = Plan(
        year=2026,
        attempts=[item("COMP1002", "2026-semester-2")],
        credits=[Credit(id="waiver", kind="WAIVER", course="COMP1002")],
    )
    r = validate(p, small_catalogue)
    assert r["course_checks"][0]["status"] == "CONDITIONAL"
    assert r["earned_units"] == 0
    assert r["degree_checks"][0]["status"] == "UNSATISFIED"


def test_no_future_offerings_are_invented(small_catalogue):
    p = Plan(year=2026, attempts=[item("COMP1001", "2028-semester-1")])
    assert validate(p, small_catalogue)["course_checks"][0]["status"] == "UNKNOWN"
    assert (
        solve(Plan(year=2026), small_catalogue, target="COMP1001", start="2028-semester-1")[
            "status"
        ]
        == "UNKNOWN"
    )


def test_path_chooses_earliest_or_branch(small_catalogue):
    result = solve(Plan(year=2026), small_catalogue, target="COMP2001")
    assert result["status"] == "VALID"
    assert result["optimal"]
    assert [(a["course"], a["term"]) for a in result["attempts"]] == [
        ("COMP1003", "2026-semester-1"),
        ("COMP2001", "2026-semester-2"),
    ]


def test_unknown_permission_cannot_be_solved(small_catalogue):
    assert solve(Plan(year=2026), small_catalogue, target="COMP2002")["status"] == "UNKNOWN"


def test_cycle_has_no_path(small_catalogue):
    for c in small_catalogue["courses"]:
        if c["code"] == "COMP1001":
            c["rules"]["prerequisite"] = compile_rule("COMP1002").model_dump()
    assert solve(Plan(year=2026), small_catalogue, target="COMP1002")["status"] != "VALID"


def test_generated_plan_validates_and_honours_load(small_catalogue):
    result = solve(Plan(year=2026, max_units=6), small_catalogue)
    assert result["status"] == "VALID"
    p = Plan(year=2026, max_units=6, attempts=result["attempts"])
    assert validate(p, small_catalogue)["status"] == "VALID"
    assert len({a.term for a in p.attempts}) == 3


def test_preferences_keep_hard_constraints(small_catalogue):
    for pref in ["earliest", "avoid_exams_early", "prefer_no_exam", "balanced"]:
        result = solve(Plan(year=2026, preference=pref), small_catalogue)
        assert result["status"] == "VALID"
        assert result["validation"]["status"] == "VALID"


def test_locked_course_not_silently_moved(small_catalogue):
    p = Plan(year=2026, attempts=[item("COMP1001", "2026-semester-2", locked=True)])
    result = solve(p, small_catalogue)
    assert result["status"] == "UNKNOWN"
    assert "Locked" in result["message"]


def test_corequisite_allowed_same_term_and_antirequisite_rejected(small_catalogue):
    for c in small_catalogue["courses"]:
        if c["code"] == "COMP1003":
            c["rules"]["corequisite"] = compile_rule("COMP1001").model_dump()
    p = Plan(year=2026, attempts=[item("COMP1001"), item("COMP1003")])
    assert all(c["status"] == "SATISFIED" for c in validate(p, small_catalogue)["course_checks"])
    for c in small_catalogue["courses"]:
        if c["code"] == "COMP1003":
            c["rules"]["antirequisite"] = compile_rule("COMP1001").model_dump()
    assert validate(p, small_catalogue)["course_checks"][1]["status"] == "UNSATISFIED"


def test_double_counting_never_silently_passes(small_catalogue):
    p = Plan(
        year=2026,
        attempts=[
            item("COMP1001", status="COMPLETED"),
            item("COMP1002", "2026-semester-2", status="COMPLETED"),
        ],
    )
    # The core courses are flagged university-wide electives, but cannot silently fill both groups.
    small_catalogue["degrees"][0]["groups"][1]["rule"]["units"] = 12
    result = validate(p, small_catalogue)
    assert result["degree_checks"][1]["status"] == "UNKNOWN"


def test_provisional_credit_marks_complete_plan_conditional(small_catalogue):
    p = Plan(
        year=2026,
        attempts=[item("COMP1002", "2026-semester-2"), item("COMP1003", "2026-semester-1")],
        credits=[Credit(id="c", kind="PROVISIONAL_CREDIT", course="COMP1001")],
    )
    result = validate(p, small_catalogue)
    assert result["status"] == "CONDITIONAL"
    assert result["earned_units"] == 0


def test_equivalence_does_not_duplicate_units(small_catalogue):
    small_catalogue["relationships"] = [
        {
            "year": 2026,
            "type": "EQUIVALENT_TO",
            "from": "COMP1003",
            "to": "COMP1001",
            "verified": True,
            "source": {"url": "fixture://reviewed-equivalence"},
        }
    ]
    p = Plan(
        year=2026,
        attempts=[item("COMP1003", status="COMPLETED"), item("COMP1002", "2026-semester-2")],
    )
    result = validate(p, small_catalogue)
    assert result["course_checks"][1]["status"] == "SATISFIED"
    assert result["degree_checks"][0]["status"] == "SATISFIED"
    assert result["earned_units"] == 6
    assert result["planned_units"] == 12
    # A single 6-unit equivalent must not satisfy a 12-unit prerequisite.
    for c in small_catalogue["courses"]:
        if c["code"] == "COMP1002":
            c["rules"]["prerequisite"] = compile_rule("12 units").model_dump()
    assert validate(p, small_catalogue)["course_checks"][1]["status"] == "UNSATISFIED"


def test_conditional_dependency_propagates(small_catalogue):
    for c in small_catalogue["courses"]:
        if c["code"] == "COMP2001":
            c["rules"]["prerequisite"] = compile_rule("COMP1002").model_dump()
    p = Plan(
        year=2026,
        attempts=[item("COMP1002", "2026-semester-2"), item("COMP2001", "2027-semester-1")],
        credits=[Credit(id="w", kind="WAIVER", course="COMP1002")],
    )
    assert [c["status"] for c in validate(p, small_catalogue)["course_checks"]] == [
        "CONDITIONAL",
        "CONDITIONAL",
    ]


def test_reviewed_incompatibility_is_enforced(small_catalogue):
    small_catalogue["relationships"] = [
        {
            "year": 2026,
            "type": "INCOMPATIBLE_WITH",
            "from": "COMP1001",
            "to": "COMP1003",
            "verified": True,
            "source": {"url": "fixture://incompatibility"},
        }
    ]
    p = Plan(year=2026, attempts=[item("COMP1001", status="COMPLETED"), item("COMP1003")])
    assert all(c["status"] == "UNSATISFIED" for c in validate(p, small_catalogue)["course_checks"])


def test_generation_keeps_locked_and_current_state(small_catalogue):
    p = Plan(year=2026, attempts=[item("COMP1001", status="CURRENT", locked=True)])
    result = solve(p, small_catalogue)
    assert result["status"] == "VALID"
    original = next(a for a in result["attempts"] if a["course"] == "COMP1001")
    assert original["id"] == "COMP1001" and original["locked"] and original["status"] == "CURRENT"
