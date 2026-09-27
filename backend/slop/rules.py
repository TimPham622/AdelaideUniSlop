"""Total, conservative requisite compiler and three-valued rule evaluator."""

from __future__ import annotations

import re
from typing import Literal

from lark import Lark, Transformer, UnexpectedInput
from pydantic import BaseModel, ConfigDict, Field, model_validator

from slop.course_codes import SOURCE_CODE_FRAGMENT, normalize_course_code

Status = Literal["SATISFIED", "UNSATISFIED", "UNKNOWN"]


class Rule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["ALL", "ANY", "COURSE", "MIN_UNITS", "EXACT_UNITS", "MAX_UNITS", "NOT", "UNKNOWN"]
    children: list[Rule] = Field(default_factory=list)
    course: str | None = None
    units: int | None = Field(default=None, ge=0)
    codes: list[str] | None = None
    level: int | None = None
    elective: bool = False
    min_selected: int = Field(default=1, ge=1)
    raw: str = ""
    warning: str | None = None

    @model_validator(mode="after")
    def shape(self):
        if self.type == "COURSE" and not self.course:
            raise ValueError("COURSE requires a course code")
        if self.type in {"MIN_UNITS", "EXACT_UNITS", "MAX_UNITS"} and self.units is None:
            raise ValueError("Unit rule requires units")
        if self.type == "NOT" and len(self.children) != 1:
            raise ValueError("NOT requires exactly one child")
        if self.type == "ANY" and len(self.children) < self.min_selected:
            raise ValueError("ANY requires enough alternatives")
        return self


_GRAMMAR = r"""
?start: expr
?expr: conjunction ("or"i conjunction)+ -> any_of
     | conjunction
?conjunction: atom ("and"i atom)+ -> all_of
            | atom
?atom: CODE -> course
     | "(" expr ")"
CODE: /[A-Z]{3,10}\s?[0-9]{3,4}[A-Z]?/
%import common.WS
%ignore WS
"""


class _Tree(Transformer):
    def course(self, xs):
        return Rule(type="COURSE", course=normalize_course_code(str(xs[0])))

    def all_of(self, xs):
        return Rule(type="ALL", children=xs)

    def any_of(self, xs):
        return Rule(type="ANY", children=xs)


_parser = Lark(_GRAMMAR, parser="lalr", transformer=_Tree())


def compile_requisite(kind: str, raw: str | None) -> Rule:
    if kind not in {"prerequisite", "corequisite", "antirequisite"}:
        raise ValueError("Unknown requisite kind")
    return compile_rule(raw, kind=kind)


def _titled_course(part: str) -> str | None:
    """Remove a clearly title-cased display name, never an arbitrary clause."""
    match = re.fullmatch(rf"({SOURCE_CODE_FRAGMENT})(?:\s+(.+))?", part.strip())
    if not match:
        return None
    title = match[2]
    if title and not re.fullmatch(
        r"[A-Z][\w'’.-]*(?:\s+(?:[A-Z][\w'’.-]*|and|for|of|the|in|to))*", title
    ):
        return None
    return normalize_course_code(match[1])


def compile_rule(raw: str | None, *, kind: str = "prerequisite") -> Rule:
    if raw is None:
        return Rule(type="UNKNOWN", warning="Requisite field is missing")
    text = re.sub(r"\s+", " ", raw).strip()
    if text.lower() in {"n/a", "none", "nil", "not applicable", "no prerequisites"}:
        return Rule(type="ALL", raw=raw)
    # Empty source is not evidence that there are no prerequisites.
    prefix = (
        r"^(?:must not have completed)\s+"
        if kind == "antirequisite"
        else r"^(?:must have completed|successful completion of|completion of)\s+"
    )
    cleaned = re.sub(
        prefix,
        "",
        text,
        flags=re.IGNORECASE,
    ).rstrip(".")
    listed = re.fullmatch(r"(all of|1 of|one of)\s+(.+)", cleaned, flags=re.IGNORECASE)
    if listed:
        parts = listed[2].split("/")
        codes = [_titled_course(part) for part in parts]
        if len(codes) >= 2 and all(codes):
            return Rule(
                type="ALL" if listed[1].lower() == "all of" else "ANY",
                children=[Rule(type="COURSE", course=c) for c in codes],
                raw=raw,
            )
    single = _titled_course(cleaned)
    if single:
        return Rule(type="COURSE", course=single, raw=raw)
    match = re.fullmatch(r"(\d+) units(?: of (?:Level|level) (\d+) study)?", cleaned)
    if match:
        return Rule(
            type="MIN_UNITS",
            units=int(match[1]),
            level=int(match[2]) if match[2] else None,
            raw=raw,
        )
    try:
        rule = _parser.parse(cleaned)
        rule.raw = raw
        return rule
    except (UnexpectedInput, ValueError):
        return Rule(
            type="UNKNOWN",
            raw=raw,
            warning="Unrecognised academic wording; review the complete source rule",
        )


def references(rule: Rule) -> set[str]:
    return (
        ({rule.course} if rule.course else set())
        | set(rule.codes or [])
        | set().union(*(references(c) for c in rule.children))
    )


def evaluate(
    rule: Rule, completed: set[str], courses: dict, aliases: set[str] | None = None
) -> dict:
    aliases = aliases or set()
    children = [evaluate(c, completed, courses, aliases) for c in rule.children]
    state: Status = "UNKNOWN"
    actual = None
    if rule.type == "UNKNOWN":
        state = "UNKNOWN"
    elif rule.type == "COURSE":
        state = (
            "UNKNOWN"
            if rule.course not in courses
            else ("SATISFIED" if rule.course in completed | aliases else "UNSATISFIED")
        )
    elif rule.type == "ALL":
        state = (
            "UNSATISFIED"
            if any(c["status"] == "UNSATISFIED" for c in children)
            else ("UNKNOWN" if any(c["status"] == "UNKNOWN" for c in children) else "SATISFIED")
        )
    elif rule.type == "ANY":
        yes = sum(c["status"] == "SATISFIED" for c in children)
        unknown = sum(c["status"] == "UNKNOWN" for c in children)
        state = (
            "SATISFIED"
            if yes >= rule.min_selected
            else ("UNKNOWN" if yes + unknown >= rule.min_selected else "UNSATISFIED")
        )
    elif rule.type == "NOT":
        state = {"SATISFIED": "UNSATISFIED", "UNSATISFIED": "SATISFIED", "UNKNOWN": "UNKNOWN"}[
            children[0]["status"]
        ]
    else:
        candidates = [
            courses[c]
            for c in completed
            if c in courses and (rule.codes is None or c in rule.codes)
        ]
        selected = [
            c
            for c in candidates
            if (rule.level is None or c["level"] == rule.level)
            and (not rule.elective or c.get("elective") is True)
        ]
        actual = sum(c.get("units") or 0 for c in selected)
        if any(c.get("units") is None for c in selected) or any(
            c not in courses for c in completed
        ) or any(
            (rule.level is not None and c.get("level") is None)
            or (rule.elective and c.get("elective") is None)
            for c in candidates
        ):
            state = "UNKNOWN"
        else:
            passed = (
                actual >= rule.units
                if rule.type == "MIN_UNITS"
                else actual <= rule.units
                if rule.type == "MAX_UNITS"
                else actual == rule.units
            )
            state = "SATISFIED" if passed else "UNSATISFIED"
    return {
        "status": state,
        "rule": rule.model_dump(),
        "children": children,
        "actual_units": actual,
    }
