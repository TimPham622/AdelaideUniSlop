"""Canonical Adelaide course identifiers observed in the source catalogue."""

import re

CODE_FRAGMENT = r"[A-Z]{3,10}\d{3,4}[A-Z]?"
SOURCE_CODE_FRAGMENT = r"[A-Z]{3,10}\s?\d{3,4}[A-Z]?"
CODE_PATTERN = re.compile(rf"^{CODE_FRAGMENT}$")


def normalize_course_code(raw: str) -> str:
    code = re.sub(r"\s+", "", raw.strip()).upper()
    if not CODE_PATTERN.fullmatch(code):
        raise ValueError(f"Invalid course code: {raw!r}")
    return code


def is_course_code(raw: str) -> bool:
    return bool(CODE_PATTERN.fullmatch(raw))
