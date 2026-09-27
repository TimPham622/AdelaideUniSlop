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


def context(data, year, degree_id="bcomp"):
    degree = next((d for d in data["degrees"] if d["year"] == year and d["id"] == degree_id), None)
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


def requirement_fit(data, year, degree_id, option, code):
    degree, courses = context(data, year, degree_id)
    groups = degree_groups(degree, option)
    if any(code in group["codes"] for group in groups):
        return "REQUIRED"
    course = courses.get(code)
    if course is None:
        return "UNKNOWN"
    if any(group["rule"]["type"] == "UNKNOWN" for group in groups):
        return "UNKNOWN"
    elective_groups = [Rule.model_validate(group["rule"]) for group in groups
                       if Rule.model_validate(group["rule"]).elective]
    if elective_groups and course.get("elective") is True:
        if course.get("units") is None or any(
            rule.level is not None and course.get("level") is None for rule in elective_groups
        ):
            return "UNKNOWN"
        if any((rule.codes is None or code in rule.codes)
               and (rule.level is None or course["level"] == rule.level)
               and (rule.type not in {"EXACT_UNITS", "MAX_UNITS"}
                    or course["units"] <= rule.units)
               for rule in elective_groups):
            return "COUNTS_AS_ELECTIVE"
    if course.get("elective") is None:
        return "UNKNOWN"
    return "OUTSIDE_KNOWN_RULES"


def resolve_course_version(data, code, period):
    return next(
        (c for c in data["courses"] if c["code"] == code and c["year"] == int(period[:4])),
        None,
    )


def can_take(plan: Plan, data, target: str, period: str):
    version = resolve_course_version(data, target, period)
    if version is None:
        return {"status": "UNKNOWN", "target": target, "period": period,
                "reasons": [{"kind": "course_version", "status": "UNKNOWN",
                             "message": "No course version is published for this calendar year"}]}
    if any(a.course == target and a.status in {"COMPLETED", "CREDIT"} for a in plan.attempts):
        return {"status": "BLOCKED", "target": target, "period": period,
                "reasons": [{"kind": "repeat", "status": "UNSATISFIED",
                             "message": "Course already completed or credited"}]}
    attempt = Attempt(id="can-take-evaluation", course=target, term=period, status="PLANNED")
    candidate = plan.model_copy(update={"attempts": [a for a in plan.attempts
        if not (a.course == target and a.term == period and a.status in {"PLANNED", "CURRENT"})]
        + [attempt]})
    report = validate(candidate, data)
    check = next(row for row in report["course_checks"] if row["id"] == attempt.id)
    status = {"SATISFIED": "TAKEABLE", "UNSATISFIED": "BLOCKED",
              "CONDITIONAL": "CONDITIONAL", "UNKNOWN": "UNKNOWN"}[check["status"]]
    return {"status": status, "target": target, "period": period,
            "reasons": check["reasons"], "source": version.get("source")}


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
    degree, program_courses = context(data, plan.year, plan.degree)
    groups = degree_groups(degree, plan.option)
    actual = {(c["year"], c["code"]): c for c in data["courses"]}
    courses = dict(program_courses)
    resolved = {}
    unresolved_versions = set()
    for attempt in sorted(plan.attempts, key=lambda a: term_order(a.term)):
        version = actual.get((int(attempt.term[:4]), attempt.course))
        if attempt.status not in {"FAILED", "WITHDRAWN"}:
            if version:
                resolved.setdefault(attempt.course, version)
            if not version or version["verification"] != "VERIFIED":
                unresolved_versions.add(attempt.course)
    courses.update(resolved)
    assumed = {c.course for c in plan.credits if c.kind == "PROVISIONAL_CREDIT"}
    waivers = {c.course for c in plan.credits if c.kind == "WAIVER"}
    checks = []
    successful = []
    conditional = []
    seen = set()
    loads = defaultdict(int)
    for attempt in sorted(plan.attempts, key=lambda a: (term_order(a.term), a.id)):
        course = actual.get((int(attempt.term[:4]), attempt.course))
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
            if course["verification"] != "VERIFIED":
                add("source", "UNKNOWN", {"message": "Course version is not source verified"})
            if attempt.course in seen:
                add(
                    "repeat",
                    "UNSATISFIED",
                    {"message": "A qualifying attempt already exists; units count once"},
                )
            if attempt.status not in {"COMPLETED", "CREDIT"}:
                loads[attempt.term] += course["units"] or 0
                offered = course
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
                rule_course = offered
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
        if result["status"] == "SATISFIED" and unresolved_versions & relevant:
            result["status"] = "UNKNOWN"
            result["message"] = "A counted course version is missing or unverified"
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
    if total_check["status"] == "SATISFIED" and unresolved_versions & projected:
        total_check["status"] = "UNKNOWN"
        total_check["message"] = "A counted course version is missing or unverified"
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
    if not chosen.get("summary_verified") or chosen.get("source_status", "SOURCE_VERIFIED") != "SOURCE_VERIFIED":
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
        "earned_units": sum(resolved[c]["units"] or 0 for c in earned if c in resolved),
        "planned_units": sum(resolved[c]["units"] or 0 for c in projected if c in resolved),
        "conditional_assumptions": [c.model_dump() for c in plan.credits],
        "unknown_count": sum(c["status"] == "UNKNOWN" for c in checks + degree_checks),
    }


def solve(plan: Plan, data, target=None, start=None):
    """CP-SAT schedules courses in observed periods. Unknowns cannot be solver shortcuts."""
    degree, program_courses = context(data, plan.year, plan.degree)
    courses = dict(program_courses)
    courses.update({c["code"]: c for c in data["courses"] if c["year"] >= plan.year})
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
            "blockers": ["MISSING_OFFERING_HORIZON"],
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
            sum((versions[int(periods[i][:4]), c]["units"] or 0) * v
                for (c, i), v in x.items() if i == t)
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
            ]
            units = sum(
                (versions[int(periods[i][:4]), c]["units"] or 0) * v
                for (c, i), v in x.items()
                if c in eligible and (i <= boundary if inclusive else i < boundary)
                and (rule.level is None or versions[int(periods[i][:4]), c]["level"] == rule.level)
                and (not rule.elective or versions[int(periods[i][:4]), c]["elective"] is True)
            )
            units += sum(
                (versions.get((int(a.term[:4]), a.course)) or courses.get(a.course, {})).get("units") or 0
                for a in earned_attempts
                if a.course in eligible and (boundary >= len(periods)
                    or term_order(a.term) < term_order(periods[boundary])
                    or (inclusive and a.term == periods[boundary]))
                and (rule.level is None or
                    (versions.get((int(a.term[:4]), a.course)) or courses.get(a.course, {})).get("level") == rule.level)
                and (not rule.elective or
                    (versions.get((int(a.term[:4]), a.course)) or courses.get(a.course, {})).get("elective") is True)
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
                    "blockers": ["LOCKED_COURSE_CONFLICT", "MISSING_OFFERING_HORIZON"],
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
                "blockers": ["UNRESOLVED_DEGREE_RULE"],
                "attempts": [],
            }
        fixed = set().union(*(set(g["codes"]) for g in groups))
        for g in groups:
            rule = Rule.model_validate(g["rule"])
            if rule.type == "UNKNOWN":
                return {
                    "status": "UNKNOWN",
                    "message": f"Unresolved degree requirement: {g['title']}",
                    "blockers": ["UNRESOLVED_DEGREE_RULE"],
                    "attempts": [],
                }
            if rule.elective:
                rule.codes = [c for c in courses if c not in fixed]
            model.add(boolean(rule, len(periods)) == 1)
        if degree["total_units"] is None:
            return {
                "status": "UNKNOWN",
                "message": "Degree unit total is unresolved",
                "blockers": ["UNRESOLVED_DEGREE_RULE"],
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
            (1000 * (len(periods) - t) if plan.preference == "avoid_exams_early" else 10000)
            * (2 if versions[int(periods[t][:4]), c]["exam"] == "EXAM" else 1) * v
            for (c, t), v in x.items()
            if versions[int(periods[t][:4]), c]["exam"] != "NO_LISTED_EXAM"
        )
    elif not target and plan.preference == "balanced":
        peak = model.new_int_var(0, len(courses), "peak_exams")
        for t in range(len(periods)):
            model.add(
                peak
                >= sum(
                    v
                    for (c, i), v in x.items()
                    if i == t and versions[int(periods[i][:4]), c]["exam"] == "EXAM"
                )
            )
        objective += peak * 1000 + sum(
            200 * v for (c, i), v in x.items()
            if versions[int(periods[i][:4]), c]["exam"] == "UNKNOWN"
        )
    model.minimize(objective)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 8
    solver.parameters.num_search_workers = 1
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        blockers = set()
        if unknown:
            blockers.add("UNPARSED_REQUISITE")
        if target and not any(code == target for code, _ in x):
            blockers.add("MISSING_OFFERING_HORIZON")
        if any(c["verification"] != "VERIFIED" for c in data["courses"]
               if c["code"] in courses and c["year"] >= plan.year):
            blockers.add("UNVERIFIED_COURSE_VERSION")
        if any((c["units"] or 0) > plan.max_units for c in data["courses"]
               if c["code"] in courses and c["year"] >= plan.year):
            blockers.add("LOAD_CONSTRAINT")
        return {
            "status": "UNKNOWN" if unknown else "INFEASIBLE",
            "message": "No verified solution within the published offering horizon. Missing offerings, unresolved rules, locked courses or the load limit may prevent a solution.",
            "unknown_rules": sorted(unknown),
            "blockers": sorted(blockers),
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
