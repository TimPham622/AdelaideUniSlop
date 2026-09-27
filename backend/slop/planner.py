"""Stateless validation and exact bounded scheduling over known offerings only."""

from __future__ import annotations

import re
from collections import defaultdict

from ortools.sat.python import cp_model

from slop.rules import Rule, evaluate
from slop.schemas import Attempt, Plan


def term_order(key):
    year, label = key.split("-", 1)
    match = re.search(r"(\d+)$", label)
    order = (
        int(match[1]) * 10
        if match
        else {"summer": 1, "autumn": 10, "winter": 15, "spring": 20}.get(label, 99)
    )
    return int(year), order, label


def context(data, year):
    degree = next((d for d in data["degrees"] if d["year"] == year), None)
    if degree is None:
        raise ValueError("Catalogue year is not available")
    courses = {c["code"]: c for c in data["courses"] if c["year"] == year}
    return degree, courses


def degree_groups(degree, option):
    if option == "general":
        return degree["groups"]
    chosen = next((o for o in degree["options"] if o["id"] == option), None)
    if chosen is None:
        raise ValueError("Unknown major for this catalogue year")
    return chosen["groups"]


def equivalents(completed, data, year):
    result = set(completed)
    changed = True
    while changed:
        previous = set(result)
        for edge in data.get("relationships", []):
            if edge.get("year") != year or not edge.get("verified") or not edge.get("source"):
                continue
            if (
                edge["type"] in {"EQUIVALENT_TO", "APPROVED_SUBSTITUTE_FOR"}
                and edge["from"] in result
            ):
                result.add(edge["to"])
            if edge["type"] == "EQUIVALENT_TO" and edge["to"] in result:
                result.add(edge["from"])
        changed = result != previous
    return result


def validate(plan: Plan, data):
    degree, courses = context(data, plan.year)
    groups = degree_groups(degree, plan.option)
    actual = {(c["year"], c["code"]): c for c in data["courses"]}
    assumed = {c.course for c in plan.credits if c.kind == "PROVISIONAL_CREDIT"}
    waivers = {c.course for c in plan.credits if c.kind == "WAIVER"}
    checks = []
    successful = []
    conditional = []
    seen = set()
    loads = defaultdict(int)
    for attempt in sorted(plan.attempts, key=lambda a: (term_order(a.term), a.id)):
        course = courses.get(attempt.course)
        row = {
            "id": attempt.id,
            "course": attempt.course,
            "term": attempt.term,
            "status": "SATISFIED",
            "reasons": [],
        }

        def add(kind, state, detail, row=row):
            row["reasons"].append({"kind": kind, "status": state, **detail})

        if not course:
            add("course", "UNKNOWN", {"message": "Course is absent from the selected catalogue"})
        elif attempt.status not in {"FAILED", "WITHDRAWN"}:
            if attempt.course in seen:
                add(
                    "repeat",
                    "UNSATISFIED",
                    {"message": "A qualifying attempt already exists; units count once"},
                )
            if attempt.status not in {"COMPLETED", "CREDIT"}:
                loads[attempt.term] += course["units"] or 0
                offered = actual.get((int(attempt.term[:4]), attempt.course))
                if not offered or not offered["offerings"]:
                    add(
                        "offering",
                        "UNKNOWN",
                        {
                            "message": "No verified offering for this calendar year; future semesters are not inferred"
                        },
                    )
                elif attempt.term not in {o["key"] for o in offered["offerings"]}:
                    add(
                        "offering",
                        "UNSATISFIED",
                        {"message": "Course is not listed in this teaching period"},
                    )
                rule_course = offered or course
                if rule_course.get("source_notices"):
                    add(
                        "source_notice",
                        "UNKNOWN",
                        {
                            "message": "Official notice requires review: "
                            + " ".join(rule_course["source_notices"])
                        },
                    )
                before = {
                    a.course for a in successful if term_order(a.term) < term_order(attempt.term)
                }
                same = {
                    a.course
                    for a in plan.attempts
                    if a.term == attempt.term
                    and a.status not in {"FAILED", "WITHDRAWN"}
                    and a.course != attempt.course
                }
                conditional_before = {
                    a.course for a in conditional if term_order(a.term) < term_order(attempt.term)
                }
                for kind in ["prerequisite", "corequisite", "antirequisite"]:
                    rule = Rule.model_validate(rule_course["rules"][kind])
                    available = before | same if kind == "corequisite" else before
                    if kind == "antirequisite":
                        if rule.type == "ALL" and not rule.children:
                            continue
                        available = {
                            a.course
                            for a in plan.attempts
                            if a.status not in {"FAILED", "WITHDRAWN"}
                            and a.course != attempt.course
                        }
                        rule = Rule(type="NOT", children=[rule], raw=rule.raw)
                    aliases = equivalents(available, data, int(attempt.term[:4]))
                    result = evaluate(rule, available, courses, aliases)
                    if result["status"] != "SATISFIED":
                        assumed_available = available | assumed | conditional_before
                        assumed_result = evaluate(
                            rule,
                            assumed_available,
                            courses,
                            equivalents(assumed_available, data, int(attempt.term[:4])),
                        )
                        if kind == "prerequisite" and (
                            attempt.course in waivers or assumed_result["status"] == "SATISFIED"
                        ):
                            add(
                                kind,
                                "CONDITIONAL",
                                {
                                    "message": "Depends on a local provisional credit or waiver",
                                    "evaluation": result,
                                },
                            )
                        else:
                            add(
                                kind,
                                result["status"],
                                {
                                    "message": rule.raw
                                    or rule.warning
                                    or "Requisite is not satisfied",
                                    "evaluation": result,
                                },
                            )
            seen.add(attempt.course)
        states = {r["status"] for r in row["reasons"]}
        row["status"] = (
            "UNSATISFIED"
            if "UNSATISFIED" in states
            else "UNKNOWN"
            if "UNKNOWN" in states
            else "CONDITIONAL"
            if "CONDITIONAL" in states
            else "SATISFIED"
        )
        if attempt.status not in {"FAILED", "WITHDRAWN"} and row["status"] == "SATISFIED":
            successful.append(attempt)
        elif attempt.status not in {"FAILED", "WITHDRAWN"} and row["status"] == "CONDITIONAL":
            conditional.append(attempt)
        checks.append(row)
    qualifying = {a.course for a in plan.attempts if a.status not in {"FAILED", "WITHDRAWN"}}
    for edge in data.get("relationships", []):
        if (
            edge.get("year") == plan.year
            and edge.get("verified")
            and edge.get("source")
            and edge["type"] == "INCOMPATIBLE_WITH"
            and {edge["from"], edge["to"]} <= qualifying
        ):
            for row in checks:
                if row["course"] in {edge["from"], edge["to"]}:
                    row["status"] = "UNSATISFIED"
                    row["reasons"].append(
                        {
                            "kind": "incompatibility",
                            "status": "UNSATISFIED",
                            "message": f"Verified incompatibility: {edge['from']} and {edge['to']}",
                            "source": edge["source"],
                        }
                    )
    for row in checks:
        if loads[row["term"]] > plan.max_units:
            row["status"] = "UNSATISFIED"
            row["reasons"].append(
                {
                    "kind": "load",
                    "status": "UNSATISFIED",
                    "message": f"Period exceeds your {plan.max_units}-unit limit",
                }
            )
    earned = {a.course for a in plan.attempts if a.status in {"COMPLETED", "CREDIT"}}
    projected = {a.course for a in plan.attempts if a.status not in {"FAILED", "WITHDRAWN"}}
    fixed_codes = set().union(*(set(g["codes"]) for g in groups))
    fixed_codes |= {c for c in projected if equivalents({c}, data, plan.year) & fixed_codes}
    degree_checks = []
    allocated = set()
    for group in groups:
        rule = Rule.model_validate(group["rule"])
        relevant = projected - fixed_codes if rule.elective else projected
        earned_relevant = earned - fixed_codes if rule.elective else earned
        result = evaluate(rule, relevant, courses, equivalents(relevant, data, plan.year))
        if (
            rule.elective
            and result["status"] == "UNSATISFIED"
            and evaluate(rule, projected, courses)["status"] == "SATISFIED"
        ):
            result["status"] = "UNKNOWN"
            result["message"] = "Would require double-counting; program policy is unverified"
        overlap = allocated & set(group["codes"]) & projected
        if overlap and degree.get("double_counting", "UNKNOWN") == "UNKNOWN":
            result["status"] = "UNKNOWN"
            result["message"] = (
                "Overlapping requirement allocation needs a reviewed double-counting policy"
            )
        allocated.update(group["codes"])
        if (
            result["status"] == "UNSATISFIED"
            and evaluate(
                rule, relevant | assumed, courses, equivalents(relevant | assumed, data, plan.year)
            )["status"]
            == "SATISFIED"
        ):
            result["status"] = "CONDITIONAL"
        degree_checks.append(
            {
                "id": group["id"],
                "title": group["title"],
                "raw": group["raw"],
                **result,
                "earned": evaluate(
                    rule, earned_relevant, courses, equivalents(earned_relevant, data, plan.year)
                ),
            }
        )
    total_rule = (
        Rule(type="EXACT_UNITS", units=degree["total_units"])
        if degree["total_units"] is not None
        else Rule(type="UNKNOWN", warning="Total units missing")
    )
    degree_checks.append(
        {
            "id": "total",
            "title": "Total degree units",
            **evaluate(total_rule, projected, courses),
            "earned": evaluate(total_rule, earned, courses),
        }
    )
    total_check = degree_checks[-1]
    if (
        total_check["status"] == "UNSATISFIED"
        and evaluate(total_rule, projected | assumed, courses)["status"] == "SATISFIED"
    ):
        total_check["status"] = "CONDITIONAL"
    chosen = (
        degree
        if plan.option == "general"
        else next(o for o in degree["options"] if o["id"] == plan.option)
    )
    if not chosen.get("summary_verified"):
        degree_checks.append(
            {
                "id": "summary",
                "title": "Program structure",
                "status": "UNKNOWN",
                "rule": {"raw": degree["summary_raw"]},
            }
        )
    all_states = {r["status"] for r in checks + degree_checks}
    overall = (
        "INVALID"
        if "UNSATISFIED" in all_states
        else "UNKNOWN"
        if "UNKNOWN" in all_states
        else "CONDITIONAL"
        if "CONDITIONAL" in all_states
        else "VALID"
    )
    return {
        "status": overall,
        "course_checks": checks,
        "degree_checks": degree_checks,
        "earned_units": sum(courses[c]["units"] or 0 for c in earned if c in courses),
        "planned_units": sum(courses[c]["units"] or 0 for c in projected if c in courses),
        "conditional_assumptions": [c.model_dump() for c in plan.credits],
        "unknown_count": sum(c["status"] == "UNKNOWN" for c in checks + degree_checks),
    }


def solve(plan: Plan, data, target=None, start=None):
    """CP-SAT schedules courses in observed periods. Unknowns cannot be solver shortcuts."""
    degree, courses = context(data, plan.year)
    groups = degree_groups(degree, plan.option)
    if target and target not in courses:
        return {"status": "UNKNOWN", "message": "Target is not in this catalogue", "attempts": []}
    earned_attempts = [a for a in plan.attempts if a.status in {"COMPLETED", "CREDIT"}]
    earned = {a.course for a in earned_attempts}
    if target in earned:
        return {
            "status": "VALID",
            "message": "Target already completed",
            "attempts": [],
            "optimal": True,
        }
    versions = {(c["year"], c["code"]): c for c in data["courses"]}
    periods = sorted(
        {
            o["key"]
            for c in data["courses"]
            for o in c["offerings"]
            if o["year"] >= plan.year and (not start or term_order(o["key"]) >= term_order(start))
        },
        key=term_order,
    )
    if not periods:
        return {
            "status": "UNKNOWN",
            "message": "No verified teaching periods are available for this horizon",
            "attempts": [],
        }
    model = cp_model.CpModel()
    x = {}
    for code in courses:
        if code in earned:
            continue
        for t, period in enumerate(periods):
            c = versions.get((int(period[:4]), code))
            if (
                c
                and c["verification"] == "VERIFIED"
                and any(o["key"] == period for o in c["offerings"])
                and c["units"] is not None
            ):
                x[code, t] = model.new_bool_var(f"{code}@{period}")
    selected = {code: sum(x.get((code, t), 0) for t in range(len(periods))) for code in courses}
    for expr in selected.values():
        model.add(expr <= 1)
    for t in range(len(periods)):
        model.add(
            sum((courses[c]["units"] or 0) * v for (c, i), v in x.items() if i == t)
            <= plan.max_units
        )
    unknown = set()
    counter = 0

    def presence(code, boundary, inclusive=False, use_equivalents=True):
        qualifying_earned = {
            a.course
            for a in earned_attempts
            if boundary >= len(periods)
            or term_order(a.term) < term_order(periods[boundary])
            or (inclusive and a.term == periods[boundary])
        }
        if use_equivalents and code in equivalents(qualifying_earned, data, plan.year):
            return 1
        if code in earned:
            # Completion cannot satisfy a prerequisite in an earlier period.
            return int(
                any(
                    a.course == code
                    and (
                        boundary >= len(periods)
                        or term_order(a.term) < term_order(periods[boundary])
                        or (inclusive and a.term == periods[boundary])
                    )
                    for a in earned_attempts
                )
            )
        return sum(
            v
            for (c, i), v in x.items()
            if c == code and (i <= boundary if inclusive else i < boundary)
        )

    def boolean(rule, boundary, inclusive=False):
        nonlocal counter
        counter += 1
        b = model.new_bool_var(f"rule{counter}")
        if rule.type == "UNKNOWN":
            unknown.add(rule.warning or rule.raw)
            model.add(b == 0)
        elif rule.type == "COURSE":
            model.add(b == presence(rule.course, boundary, inclusive))
        elif rule.type in {"ALL", "ANY"}:
            children = [boolean(c, boundary, inclusive) for c in rule.children]
            needed = len(children) if rule.type == "ALL" else rule.min_selected
            model.add(sum(children) >= needed).only_enforce_if(b)
            model.add(sum(children) < needed).only_enforce_if(b.Not())
        elif rule.type == "NOT":
            model.add(b + boolean(rule.children[0], boundary, inclusive) == 1)
        else:
            eligible = [
                c
                for c in courses
                if (rule.codes is None or c in rule.codes)
                and (rule.level is None or courses[c]["level"] == rule.level)
                and (not rule.elective or courses[c]["elective"] is True)
            ]
            units = sum(
                (courses[c]["units"] or 0) * presence(c, boundary, inclusive, use_equivalents=False)
                for c in eligible
            )
            if rule.type == "MIN_UNITS":
                model.add(units >= rule.units).only_enforce_if(b)
                model.add(units < rule.units).only_enforce_if(b.Not())
            elif rule.type == "MAX_UNITS":
                model.add(units <= rule.units).only_enforce_if(b)
                model.add(units > rule.units).only_enforce_if(b.Not())
            else:
                model.add(units == rule.units).only_enforce_if(b)
                model.add(units != rule.units).only_enforce_if(b.Not())
        return b

    for (code, t), v in x.items():
        c = versions[int(periods[t][:4]), code]
        for kind in ["prerequisite", "corequisite"]:
            rule = Rule.model_validate(c["rules"][kind])
            model.add(v <= boolean(rule, t, kind == "corequisite"))
        anti = Rule.model_validate(c["rules"]["antirequisite"])
        if not (anti.type == "ALL" and not anti.children):
            model.add(v + boolean(anti, len(periods)) <= 1)
    for edge in data.get("relationships", []):
        if (
            edge.get("year") == plan.year
            and edge.get("verified")
            and edge.get("source")
            and edge["type"] == "INCOMPATIBLE_WITH"
        ):
            model.add(
                presence(edge["from"], len(periods), use_equivalents=False)
                + presence(edge["to"], len(periods), use_equivalents=False)
                <= 1
            )
    retained = [
        a for a in plan.attempts if a.status in {"COMPLETED", "CREDIT", "FAILED", "WITHDRAWN"}
    ]
    for a in plan.attempts:
        if a.status in {"CURRENT", "PLANNED"} and (a.locked or a.status == "CURRENT"):
            if a.term not in periods or (a.course, periods.index(a.term)) not in x:
                return {
                    "status": "UNKNOWN",
                    "message": f"Locked {a.course} has no verified offering in {a.term}",
                    "attempts": [],
                }
            model.add(x[a.course, periods.index(a.term)] == 1)
    if target:
        model.add(selected[target] == 1)
    else:
        chosen = (
            degree
            if plan.option == "general"
            else next(o for o in degree["options"] if o["id"] == plan.option)
        )
        if not chosen.get("summary_verified"):
            return {
                "status": "UNKNOWN",
                "message": "Program structure requires source review",
                "attempts": [],
            }
        fixed = set().union(*(set(g["codes"]) for g in groups))
        for g in groups:
            rule = Rule.model_validate(g["rule"])
            if rule.type == "UNKNOWN":
                return {
                    "status": "UNKNOWN",
                    "message": f"Unresolved degree requirement: {g['title']}",
                    "attempts": [],
                }
            if rule.elective:
                rule.codes = [c for c in courses if c not in fixed]
            model.add(boolean(rule, len(periods)) == 1)
        if degree["total_units"] is None:
            return {
                "status": "UNKNOWN",
                "message": "Degree unit total is unresolved",
                "attempts": [],
            }
        model.add(boolean(Rule(type="EXACT_UNITS", units=degree["total_units"]), len(periods)) == 1)
    finish = model.new_int_var(0, len(periods), "finish")
    for (code, t), v in x.items():
        if not target or code == target:
            model.add(finish >= (t + 1) * v)
    objective = finish * 100000 + sum((t + 1) * 10 * v + v for (c, t), v in x.items())
    if not target and plan.preference in {"avoid_exams_early", "prefer_no_exam"}:
        objective += sum(
            (1000 * (len(periods) - t) if plan.preference == "avoid_exams_early" else 10000) * v
            for (c, t), v in x.items()
            if courses[c]["exam"] != "NO_LISTED_EXAM"
        )
    elif not target and plan.preference == "balanced":
        peak = model.new_int_var(0, len(courses), "peak_exams")
        for t in range(len(periods)):
            model.add(
                peak
                >= sum(
                    v
                    for (c, i), v in x.items()
                    if i == t and courses[c]["exam"] != "NO_LISTED_EXAM"
                )
            )
        objective += peak * 1000
    model.minimize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 8
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": "UNKNOWN" if unknown else "INFEASIBLE",
            "message": "No verified solution within the published offering horizon. Missing offerings, unresolved rules, locked courses or the load limit may prevent a solution.",
            "unknown_rules": sorted(unknown),
            "horizon": periods,
            "attempts": [],
        }
    generated = [
        Attempt(id=f"generated-{c}-{periods[t]}", course=c, term=periods[t], status="PLANNED")
        for (c, t), v in x.items()
        if solver.value(v)
    ]
    originals = {(a.course, a.term): a for a in plan.attempts if a.status in {"CURRENT", "PLANNED"}}
    generated = [originals.get((a.course, a.term), a) for a in generated]
    candidate = plan.model_copy(
        update={
            "attempts": retained + sorted(generated, key=lambda a: (term_order(a.term), a.course))
        }
    )
    report = validate(candidate, data)
    check_states = {c["status"] for c in report["course_checks"]}
    safe = not (check_states & {"UNSATISFIED", "UNKNOWN", "CONDITIONAL"}) and (
        bool(target) or report["status"] == "VALID"
    )
    return {
        "status": "VALID" if safe else "UNKNOWN",
        "message": ("Earliest verified prerequisite path" if target else "Verified remaining plan")
        if safe
        else "Candidate requires review; not a confirmed valid plan",
        "optimal": status == cp_model.OPTIMAL,
        "attempts": [a.model_dump() for a in candidate.attempts],
        "validation": report,
        "horizon": periods,
    }
