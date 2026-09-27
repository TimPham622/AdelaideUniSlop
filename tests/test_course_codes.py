import json
from pathlib import Path

from slop.course_codes import is_course_code, normalize_course_code
from slop.schemas import Attempt


def test_shared_course_code_contract():
    cases = json.loads(Path("data/course_code_cases.json").read_text())
    assert all(is_course_code(code) for code in cases["valid"])
    assert not any(is_course_code(code) for code in cases["invalid"])
    assert normalize_course_code("STAT X100") == "STATX100"
    assert Attempt(id="x", course="STATX100", term="2027-semester-1").course == "STATX100"
