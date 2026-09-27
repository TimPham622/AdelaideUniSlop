"""Explicit DTO for raw courses-api exports; never a runtime dependency."""

from pydantic import BaseModel, Field

from slop.db import digest
from slop.ingestion import PARSER_VERSION
from slop.rules import compile_rule


class UpstreamCourse(BaseModel):
    code: str = Field(pattern=r"^[A-Z]{3,8}\d{4}$")
    year: int = Field(ge=2020, le=2100)
    title: str
    course_id: str | int | None = None
    units: int | None = None
    course_overview: str = ""
    learning_outcomes: list[str] = Field(default_factory=list)
    assessments: list[str] = Field(default_factory=list)
    terms: list[str] = Field(default_factory=list)
    prerequisites: str | None = None
    corequisites: str | None = None
    antirequisites: str | None = None
    university_wide_elective: bool | None = None
    source_url: str
    fetched_at: str

    def normalized(self):
        raw = {
            "prerequisite": self.prerequisites,
            "corequisite": self.corequisites,
            "antirequisite": self.antirequisites,
        }
        import re

        return {
            "code": self.code,
            "year": self.year,
            "identity": str(self.course_id or self.code),
            "title": self.title,
            "units": self.units,
            "level": int(self.code[-4]),
            "overview": self.course_overview,
            "outcomes": self.learning_outcomes,
            "assessments": self.assessments,
            "exam": (
                "EXAM"
                if any(
                    re.search(r"\bexam(?:ination)?\b", a, re.IGNORECASE) for a in self.assessments
                )
                else "NO_LISTED_EXAM"
            )
            if self.assessments
            else "UNKNOWN",
            "elective": self.university_wide_elective,
            "raw": raw,
            "rules": {k: compile_rule(v).model_dump() for k, v in raw.items()},
            "offerings": [
                {
                    "key": f"{self.year}-" + re.sub("[^a-z0-9]+", "-", t.lower()).strip("-"),
                    "label": t,
                    "year": self.year,
                    "order": i,
                }
                for i, t in enumerate(self.terms)
            ],
            "verification": "VERIFIED",
            "warnings": [],
            "source": {
                "requested_url": self.source_url,
                "canonical_url": self.source_url,
                "year": self.year,
                "fetched_at": self.fetched_at,
                "sha256": digest(self.model_dump()),
                "parser_version": PARSER_VERSION,
                "upstream": "compsci-adl/courses-api raw export",
            },
        }
