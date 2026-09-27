from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Attempt(Strict):
    id: str = Field(min_length=1, max_length=100)
    course: str = Field(pattern=r"^[A-Z]{3,8}\d{4}[A-Z]?$", max_length=20)
    term: str = Field(pattern=r"^\d{4}-[a-z0-9-]+$", max_length=80)
    status: Literal["PLANNED", "CURRENT", "COMPLETED", "FAILED", "WITHDRAWN", "CREDIT"] = "PLANNED"
    locked: bool = False


class Credit(Strict):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal["PROVISIONAL_CREDIT", "WAIVER"]
    course: str = Field(pattern=r"^[A-Z]{3,8}\d{4}[A-Z]?$")
    note: str = Field(default="", max_length=1000)


class Plan(Strict):
    schema_version: Literal[1] = 1
    name: str = Field(default="My computer science plan", min_length=1, max_length=100)
    year: int = Field(ge=2020, le=2100)
    degree: Literal["bcomp"] = "bcomp"
    option: str = Field(default="general", max_length=150)
    attempts: list[Attempt] = Field(default_factory=list, max_length=200)
    credits: list[Credit] = Field(default_factory=list, max_length=100)
    max_units: int = Field(default=24, ge=6, le=48)
    preference: Literal["earliest", "avoid_exams_early", "prefer_no_exam", "balanced"] = "earliest"

    @model_validator(mode="after")
    def unique_ids(self):
        ids = [a.id for a in self.attempts]
        if len(ids) != len(set(ids)):
            raise ValueError("Attempt IDs must be unique")
        credit_ids = [c.id for c in self.credits]
        if len(credit_ids) != len(set(credit_ids)):
            raise ValueError("Credit IDs must be unique")
        return self


class PathRequest(Strict):
    plan: Plan
    target: str = Field(pattern=r"^[A-Z]{3,8}\d{4}[A-Z]?$")
    start: str | None = Field(default=None, pattern=r"^\d{4}-[a-z0-9-]+$")


class SearchRequest(Strict):
    query: str = Field(min_length=1, max_length=400)
    year: int = Field(ge=2020, le=2100)
    compatible_first: bool = True
    limit: int = Field(default=20, ge=1, le=50)
