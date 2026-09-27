import pytest
from slop.rules import Rule, compile_requisite, compile_rule, evaluate


@pytest.mark.parametrize(
    "raw",
    [
        "COMP1001 and (COMP1002 or COMP1003)",
        "COMP1001 or COMP1002 and COMP1003",
        "must have completed COMP1001",
        "18 units of Level 2 study",
        "N/A",
    ],
)
def test_known_grammar(raw):
    assert compile_rule(raw).type != "UNKNOWN"


@pytest.mark.parametrize(
    "raw",
    [
        None,
        "",
        "COMP1001 and permission of the coordinator",
        "COMP1001 with a distinction",
        "18 units in approved electives",
        "COMP1001 / COMP1002",
        "COMP1001 except for transfer students",
    ],
)
def test_whole_unfamiliar_clause_is_preserved(raw):
    rule = compile_rule(raw)
    assert rule.type == "UNKNOWN"
    assert rule.warning
    if raw is not None:
        assert rule.raw == raw


def test_three_valued_logic_and_precedence(small_catalogue):
    courses = {c["code"]: c for c in small_catalogue["courses"]}
    rule = compile_rule("COMP1001 or COMP1002 and COMP1003")
    assert evaluate(rule, {"COMP1001"}, courses)["status"] == "SATISFIED"
    assert evaluate(rule, {"COMP1002"}, courses)["status"] == "UNSATISFIED"
    r = Rule(type="ANY", children=[compile_rule(None), compile_rule("COMP1001")])
    assert evaluate(r, set(), courses)["status"] == "UNKNOWN"
    assert evaluate(r, {"COMP1001"}, courses)["status"] == "SATISFIED"
    assert evaluate(compile_rule("COMP9999"), {"COMP9999"}, courses)["status"] == "UNKNOWN"


def test_invalid_ast_is_rejected():
    with pytest.raises(ValueError):
        Rule(type="NOT")
    with pytest.raises(ValueError):
        Rule(type="COURSE")
    with pytest.raises(ValueError):
        Rule(type="EXACT_UNITS")


def test_explicit_slash_lists_keep_all_vs_one():
    assert compile_rule("must have completed all of COMP1001/COMP1002").type == "ALL"
    assert compile_rule("must have completed 1 of COMP1001/COMP1002").type == "ANY"
    assert compile_rule("COMP1001/COMP1002").type == "UNKNOWN"


def test_official_title_bearing_requisites_preserve_raw_and_logic():
    raw = ("Must have completed all of COMP1002 Problem Solving and Programming/"
           "MATH1022 Maths for Machine Learning/STATX100 Probability and Statistics")
    rule = compile_requisite("prerequisite", raw)
    assert rule.type == "ALL" and rule.raw == raw
    assert [child.course for child in rule.children] == ["COMP1002", "MATH1022", "STATX100"]
    anti = compile_requisite("antirequisite", "Must not have completed ARTI2001 Machine Learning")
    assert anti.type == "COURSE" and anti.course == "ARTI2001"
    assert compile_requisite("prerequisite", "Must have completed one of COMP1002 Problem Solving/COMP1003 Structured Data").type == "ANY"
    ambiguous = ("Must have completed Must have completed ARTI6003 OR COMP6035 Machine "
                 "Learning Algorithms AND ARTI2001 OR COMP2052 Machine Learning")
    assert compile_requisite("prerequisite", ambiguous).type == "UNKNOWN"
