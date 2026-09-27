"""Adapter for a raw courses-api Course ORM export, not its reduced public API.

Contract: https://github.com/compsci-adl/courses-api/blob/main/src/models.py
The export must include raw requisite strings. A public detail response whose
``requirements`` contain only code lists cannot certify the original logic.
"""

import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from slop.course_codes import CODE_FRAGMENT, normalize_course_code
from slop.db import digest
from slop.ingestion import PARSER_VERSION
from slop.rules import compile_requisite


class UpstreamCourse(BaseModel):
    id: str
    course_id: int
    course_code: str = Field(pattern=rf"^{CODE_FRAGMENT}$")
    year: int = Field(ge=2020, le=2100)
    title: str
    units: int | None = None
    course_level: str | None = None
    course_overview: str | None = None
    learning_outcomes: list[dict[str, Any]] = Field(default_factory=list)
    assessments: list[dict[str, Any]] = Field(default_factory=list)
    terms: str | list[str]
    prerequisites: str | None = None
    corequisites: str | None = None
    antirequisites: str | None = None
    university_wide_elective: bool | None = None
    url: str
    fetched_at: str | None = None

    @field_validator("course_code")
    @classmethod
    def canonical_code(cls, code: str) -> str:
        return normalize_course_code(code)

    def normalized(self):
        raw = {
            "prerequisite": self.prerequisites,
            "corequisite": self.corequisites,
            "antirequisite": self.antirequisites,
        }
        level_match = re.fullmatch(r"(?:Level\s*)?(\d+)", self.course_level or "", re.IGNORECASE)
        terms = self.terms.split(",") if isinstance(self.terms, str) else self.terms
        terms = [term.strip() for term in terms if term.strip()]
        assessments = [
            " – ".join(str(part) for part in (a.get("title"), a.get("weighting")) if part)
            for a in self.assessments
        ]
        source = {
            "requested_url": self.url,
            "canonical_url": self.url,
            "year": self.year,
            "fetched_at": self.fetched_at,
            "sha256": digest(self.model_dump()),
            "parser_version": PARSER_VERSION,
            "upstream": "compsci-adl/courses-api raw Course ORM export",
        }
        return {
            "code": self.course_code,
            "year": self.year,
            "identity": str(self.course_id),
            "title": self.title,
            "units": self.units,
            "level": int(level_match[1]) if level_match else None,
            "level_source": "UPSTREAM_FIELD" if level_match else "UNKNOWN",
            "overview": self.course_overview or "",
            "outcomes": [o["description"] for o in self.learning_outcomes if o.get("description")],
            "assessments": assessments,
            "exam": (
                "EXAM"
                if any(re.search(r"\bexam(?:ination)?\b", a, re.IGNORECASE) for a in assessments)
                else "NO_LISTED_EXAM"
            ) if assessments else "UNKNOWN",
            "elective": self.university_wide_elective,
            "raw": raw,
            "rules": {k: compile_requisite(k, v).model_dump() for k, v in raw.items()},
            "offerings": [
                {
                    "key": f"{self.year}-" + re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-"),
                    "label": term,
                    "year": self.year,
                    "order": index,
                }
                for index, term in enumerate(terms)
                if re.fullmatch(r"(?:Semester|Trimester|Term)\s+\d+|Summer|Winter|Spring|Autumn", term, re.IGNORECASE)
            ],
            "source": source,
            "verification": "UNKNOWN",
            "source_status": "SOURCE_UNVERIFIED",
            "parse_status": "PARSED" if all(compile_requisite(k, v).type != "UNKNOWN"
                for k, v in raw.items()) else "UNPARSED",
            "warnings": ["Upstream raw export has not been independently verified against the official page"],
        }
