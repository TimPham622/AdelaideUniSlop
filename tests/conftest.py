import copy

import pytest
from slop.rules import compile_rule


@pytest.fixture
def small_catalogue():
    def course(code, prerequisite="N/A", terms=(1, 2), exam="NO_LISTED_EXAM", year=2026):
        return {
            "code": code,
            "title": code,
            "identity": code,
            "year": year,
            "units": 6,
            "level": int(code[-4]),
            "overview": "",
            "outcomes": [],
            "assessments": [],
            "exam": exam,
            "elective": True,
            "verification": "VERIFIED",
            "warnings": [],
            "offerings": [
                {"key": f"{year}-semester-{t}", "label": f"Semester {t}", "year": year, "order": t}
                for t in terms
            ],
            "raw": {"prerequisite": prerequisite, "corequisite": "N/A", "antirequisite": "N/A"},
            "rules": {
                "prerequisite": compile_rule(prerequisite).model_dump(),
                "corequisite": compile_rule("N/A").model_dump(),
                "antirequisite": compile_rule("N/A").model_dump(),
            },
        }

    courses = [
        course("COMP1001", terms=(1,)),
        course("COMP1002", "COMP1001", terms=(2,)),
        course("COMP1003", exam="EXAM"),
        course("COMP2001", "COMP1002 or COMP1003"),
        course("COMP2002", "permission of the coordinator"),
    ]
    later = copy.deepcopy(courses)
    for c in later:
        c["year"] = 2027
        for o in c["offerings"]:
            o["year"] = 2027
            o["key"] = o["key"].replace("2026", "2027")
    return {
        "degrees": [
            {
                "id": "bcomp",
                "year": 2026,
                "total_units": 18,
                "summary_verified": True,
                "double_counting": "UNKNOWN",
                "course_references": {"COMP1001": {}, "COMP1002": {}},
                "options": [],
                "groups": [
                    {
                        "id": "core",
                        "title": "Core",
                        "raw": "All core courses",
                        "codes": ["COMP1001", "COMP1002"],
                        "rule": {
                            "type": "ALL",
                            "children": [
                                {"type": "COURSE", "course": "COMP1001"},
                                {"type": "COURSE", "course": "COMP1002"},
                            ],
                        },
                    },
                    {
                        "id": "electives",
                        "title": "Electives",
                        "raw": "6 elective units",
                        "codes": [],
                        "rule": {"type": "EXACT_UNITS", "units": 6, "elective": True},
                    },
                ],
            }
        ],
        "courses": courses + later,
        "relationships": [],
    }
