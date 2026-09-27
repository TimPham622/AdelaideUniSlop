"""Public-source ingestion. Raw HTML is kept only in the private, expiring cache."""

from __future__ import annotations

import hashlib
import json
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from slop.course_codes import SOURCE_CODE_FRAGMENT, normalize_course_code
from slop.rules import compile_requisite, references

PARSER_VERSION = "adelaide-1.1.0"
ORIGIN = "https://adelaide.edu.au"
AGENT = "AdelaideUniSlopCatalogue/0.1 (public academic catalogue; 1 request/second)"
CODE = SOURCE_CODE_FRAGMENT


def clean(el) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip() if el else ""


class Fetcher:
    def __init__(self, cache=Path(".cache/adelaide"), ttl=86400):
        self.cache, self.ttl = Path(cache), ttl
        self.cache.mkdir(parents=True, exist_ok=True)
        self.client = httpx.Client(
            timeout=45, headers={"User-Agent": AGENT}, follow_redirects=False
        )
        self.last = 0.0
        self.robots = None

    def _request(self, url, headers=None):
        for attempt in range(4):
            time.sleep(max(0, 1 - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            response = self.client.get(url, headers=headers)
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            retry = response.headers.get("Retry-After", "")
            try:
                delay = float(retry)
            except ValueError:
                try:
                    delay = max(
                        0, (parsedate_to_datetime(retry) - datetime.now(UTC)).total_seconds()
                    )
                except (ValueError, TypeError):
                    delay = 2 ** (attempt + 1)
            if delay > 300:
                raise RuntimeError("Origin requested a long pause; retry ingestion later")
            time.sleep(delay)
        response.raise_for_status()
        return response

    def fetch(self, url, year):
        parsed = urlparse(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "adelaide.edu.au"
            or not parsed.path.startswith("/study/")
        ):
            raise ValueError("Only official Adelaide study URLs are permitted")
        if self.robots is None:
            r = self._request(ORIGIN + "/robots.txt")
            r.raise_for_status()
            self.robots = RobotFileParser()
            self.robots.parse(r.text.splitlines())
        if not self.robots.can_fetch(AGENT, url):
            raise RuntimeError("robots.txt disallows this URL")
        key = hashlib.sha256(url.encode()).hexdigest()
        meta_file, html_file = self.cache / f"{key}.json", self.cache / f"{key}.html"
        old = (
            json.loads(meta_file.read_text()) if meta_file.exists() and html_file.exists() else None
        )
        if old and time.time() - html_file.stat().st_mtime < self.ttl:
            return html_file.read_text(), {**old, "parser_version": PARSER_VERSION}
        headers = {}
        if old:
            if old.get("etag"):
                headers["If-None-Match"] = old["etag"]
            if old.get("last_modified"):
                headers["If-Modified-Since"] = old["last_modified"]
        target = url
        for _ in range(6):
            if (
                urlparse(target).scheme != "https"
                or urlparse(target).netloc != "adelaide.edu.au"
                or not urlparse(target).path.startswith("/study/")
                or not self.robots.can_fetch(AGENT, target)
            ):
                raise RuntimeError("Unsafe or disallowed source redirect")
            r = self._request(target, headers)
            if r.status_code in {301, 302, 303, 307, 308}:
                target = urljoin(target, r.headers["location"])
                continue
            break
        if r.status_code == 304 and old:
            html_file.touch()
            return html_file.read_text(), {**old, "parser_version": PARSER_VERSION}
        if r.status_code != 404:
            r.raise_for_status()
        html = r.text
        meta = {
            "requested_url": url,
            "status_code": r.status_code,
            "canonical_url": str(r.url),
            "year": year,
            "fetched_at": datetime.now(UTC).isoformat(),
            "sha256": hashlib.sha256(r.content).hexdigest(),
            "parser_version": PARSER_VERSION,
            "etag": r.headers.get("etag"),
            "last_modified": r.headers.get("last-modified"),
        }
        html_file.write_text(html)
        meta_file.write_text(json.dumps(meta))
        return html, meta

    def prune(self, days=14):
        for file in self.cache.glob("*"):
            if file.is_file() and file.stat().st_mtime < time.time() - days * 86400:
                file.unlink()


def parse_degree(html, source):
    soup = BeautifulSoup(html, "html.parser")
    requested_year = source["year"]
    page_years = {
        int(year)
        for year in re.findall(r"/study/(?:courses|degrees)/(20\d{2})/", html)
    }
    page_year = next(iter(page_years)) if len(page_years) == 1 else None
    year_status = (
        "MATCH" if page_year == requested_year else "MISMATCH" if page_year else "UNKNOWN"
    )
    groups, options, refs = [], [], {}
    summary = clean(soup.select_one(".cmp-course-info-by-year__description"))
    for panel in soup.select(".cmp-course-info-by-year__panel"):
        key = panel.get("id")
        text = clean(panel.select_one(".cmp-course-info-by-year__accordion-info-text"))
        text = text.removesuffix(" View study plan")
        codes = []
        for row in panel.select("tbody tr"):
            values = [clean(c) for c in row.select(".table-content")]
            if len(values) >= 3 and re.fullmatch(CODE, values[1]):
                code = normalize_course_code(values[1])
                codes.append(code)
                refs[code] = {"code": code, "title": values[0], "units": int(values[2])}
        if key == "majors":
            for link in panel.select("a.table-content"):
                options.append(
                    {
                        "id": link["href"].rstrip("/").split("/")[-2],
                        "title": clean(link),
                        "source_url": link["href"],
                    }
                )
            continue
        match = re.fullmatch(r"Complete (\d+) units for ALL of the following:", text)
        if match and codes and sum(refs[c]["units"] for c in codes) == int(match[1]):
            ast = {"type": "ALL", "children": [{"type": "COURSE", "course": c} for c in codes]}
            units = int(match[1])
        elif text == "Complete 12 units comprising: 12 units from University-wide electives":
            ast = {"type": "EXACT_UNITS", "units": 12, "elective": True}
            units = 12
        else:
            ast = {
                "type": "UNKNOWN",
                "raw": text,
                "warning": "Degree group requires reviewed override",
            }
            units = None
        groups.append(
            {
                "id": key,
                "title": key.replace("-", " ").title(),
                "raw": text,
                "units": units,
                "codes": codes,
                "rule": ast,
                "verification": "UNKNOWN" if ast["type"] == "UNKNOWN" else "VERIFIED",
            }
        )
    total_match = re.match(r"Complete (\d+) units comprising:", summary)
    # Preserve the entire summary as a separate check; an unfamiliar clause cannot disappear.
    known_summary = "Complete 144 units comprising: 66 units for all Core courses , and Either: 54 units for one Major from Majors , or 54 units for all Discipline courses , and 12 units for all Work integrated learning , and 12 units for Electives"
    normal = re.sub(r"\s+([,:])", r"\1", summary)
    recognized = normal == re.sub(r"\s+([,:])", r"\1", known_summary)
    overview = soup.select_one("#section-overview")
    plan = []
    study_year, term = 1, "semester-1"
    for el in soup.select(
        ".study-plan-future-students .year-title, .study-plan-future-students .semester-title, .study-plan-future-students .course-card"
    ):
        if "year-title" in el.get("class", []):
            number = re.search(r"\d+", clean(el))
            study_year = int(number[0]) if number else study_year
        elif "semester-title" in el.get("class", []):
            term = re.sub("[^a-z0-9]+", "-", clean(el).lower()).strip("-")
        else:
            code = clean(el.select_one(".card-title__code"))
            if code:
                plan.append(
                    {
                        "course": code,
                        "term": f"{source['year'] + study_year - 1}-{term}",
                        "group": el.get("data-course-type", ""),
                    }
                )
    return {
        "id": "bcomp",
        "title": clean(soup.find("h1")),
        "year": source["year"],
        "requested_year": requested_year,
        "page_year": page_year,
        "year_status": year_status,
        "program_code": "BCOMP",
        "total_units": int(total_match[1]) if total_match else None,
        "overview": clean(overview),
        "summary_raw": summary,
        "summary_verified": recognized,
        "groups": groups,
        "options": options,
        "course_references": refs,
        "standard_plan": plan,
        "source": source,
        "source_status": (
            "SOURCE_VERIFIED" if year_status == "MATCH" else
            "SOURCE_YEAR_MISMATCH" if year_status == "MISMATCH" else "SOURCE_UNVERIFIED"
        ),
        "parse_status": "PARSED" if recognized and all(g["verification"] == "VERIFIED" for g in groups) else "UNPARSED",
        "verification": "VERIFIED"
        if year_status == "MATCH" and recognized and all(g["verification"] == "VERIFIED" for g in groups)
        else "PARTIAL",
        "double_counting": "UNKNOWN",
    }


def parse_course(html, source, code):
    if source.get("status_code") == 404:
        raise ValueError("Course source returned 404")
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup
    lines = [s.strip() for s in main.get_text("\n", strip=True).splitlines() if s.strip()]

    def value(label):
        try:
            return lines[lines.index(label) + 1]
        except (ValueError, IndexError):
            return None

    def section(label):
        heading = next(
            (h for h in main.find_all(["h2", "h3"]) if clean(h).lower() == label.lower()), None
        )
        if not heading:
            return None
        parts = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in {"h2", "h3"}:
                break
            if getattr(sibling, "get_text", None):
                parts.append(clean(sibling))
        return " ".join(p for p in parts if p) or None

    # Course detail headings live in individual components; read their content containers.
    def content(label):
        heading = next(
            (h for h in main.find_all(["h2", "h3"]) if clean(h).lower() == label.lower()), None
        )
        if not heading:
            return None
        sibling = heading.find_next_sibling()
        return clean(sibling) if sibling else None

    requisites = {
        k: content(label)
        for k, label in [
            ("prerequisite", "Prerequisite(s)"),
            ("corequisite", "Corequisite(s)"),
            ("antirequisite", "Antirequisite(s)"),
        ]
    }
    offerings = []
    for el in soup.select(".cmp-course-accordion__title"):
        label = clean(el)
        if re.match(
            r"^(Semester|Trimester|Term|Summer|Winter|Spring|Autumn)\b", label, re.IGNORECASE
        ) and label not in [o["label"] for o in offerings]:
            slug = re.sub("[^a-z0-9]+", "-", label.lower()).strip("-")
            offerings.append(
                {
                    "key": f"{source['year']}-{slug}",
                    "label": label,
                    "year": source["year"],
                    "order": len(offerings),
                }
            )
    outcomes_heading = next(
        (h for h in main.find_all("h2") if clean(h) == "Course learning outcomes"), None
    )
    outcomes_list = outcomes_heading.find_next_sibling() if outcomes_heading else None
    outcomes = [clean(li) for li in outcomes_list.select("li")] if outcomes_list else []
    assess_heading = next(
        (h for h in main.find_all(["h2", "h3"]) if clean(h) == "Assessment"), None
    )
    assess_list = assess_heading.find_next_sibling() if assess_heading else None
    assessments = [clean(li) for li in assess_list.select("li")] if assess_list else []
    title = clean(soup.find("h1"))
    if not title or "not found" in title.lower():
        raise ValueError("Missing course page")
    units = value("Unit value")
    level_text = value("Course level")
    level_match = re.fullmatch(r"(?:Level\s*)?(\d+)", level_text or "", re.IGNORECASE)
    year_evidence = re.search(r"(?:Undergraduate|Postgraduate)\s*\|\s*(\d{4})", clean(main))
    year_matches = bool(year_evidence and int(year_evidence[1]) == source["year"])
    if not year_matches:
        offerings = []
    notices = [clean(el) for el in soup.select(".cmp-alert-body-message-content") if clean(el)]
    compiled = {k: compile_requisite(k, v).model_dump() for k, v in requisites.items()}
    return {
        "code": code,
        "year": source["year"],
        "identity": value("Course ID") or code,
        "title": title,
        "units": int(units) if units and units.isdigit() else None,
        "level": int(level_match[1]) if level_match else None,
        "level_source": "OFFICIAL_FIELD" if level_match else "UNKNOWN",
        "campus": value("Campus"),
        "overview": content("Course overview") or "",
        "outcomes": outcomes,
        "assessments": assessments,
        "exam": (
            "EXAM"
            if any(re.search(r"\bexam(?:ination)?\b", a, re.IGNORECASE) for a in assessments)
            else "NO_LISTED_EXAM"
        )
        if assessments
        else "UNKNOWN",
        "elective": {"Yes": True, "No": False}.get(value("University-wide elective course")),
        "offerings": offerings,
        "raw": requisites,
        "rules": compiled,
        "source": source,
        "source_status": "SOURCE_VERIFIED" if year_matches and not notices else
            "SOURCE_YEAR_MISMATCH" if year_evidence and not year_matches else "SOURCE_UNVERIFIED",
        "parse_status": "PARSED" if all(r["type"] != "UNKNOWN" for r in compiled.values()) else "UNPARSED",
        "verification": "VERIFIED" if year_matches and not notices else "UNKNOWN",
        "source_notices": notices,
        "warnings": ([] if year_matches else ["Requested catalogue year not confirmed by page"])
        + notices,
        "requested_year": source["year"],
        "page_year": int(year_evidence[1]) if year_evidence else None,
        "year_status": "MATCH" if year_matches else "MISMATCH" if year_evidence else "UNKNOWN",
    }


def ingest(years=(2026, 2027), output=Path("data/fixtures/catalogue.json")):
    fetcher = Fetcher()
    degrees, courses = [], []
    for year in years:
        url = f"{ORIGIN}/study/degrees/{year}/bachelor-of-computer-science/dom/"
        html, source = fetcher.fetch(url, year)
        degree = parse_degree(html, source)
        degrees.append(degree)
        queue = dict(degree["course_references"])
        queue.update({c["course"]: {} for c in degree["standard_plan"]})
        for option in degree["options"]:
            path = urlparse(option["source_url"]).path
            path = re.sub(r"/study/degrees/(?:\d{4}/)?", f"/study/degrees/{year}/", path)
            option_html, option_source = fetcher.fetch(ORIGIN + path, year)
            parsed = parse_degree(option_html, option_source)
            option["groups"] = parsed["groups"]
            option["summary_raw"] = parsed["summary_raw"]
            option["summary_verified"] = parsed["summary_verified"]
            option["source"] = option_source
            option["verification"] = parsed["verification"]
            option["source_status"] = parsed["source_status"]
            option["parse_status"] = parsed["parse_status"]
            option["requested_year"] = parsed["requested_year"]
            option["page_year"] = parsed["page_year"]
            option["year_status"] = parsed["year_status"]
            option["standard_plan"] = parsed["standard_plan"]
            queue.update(parsed["course_references"])
        seen = set()
        while queue:
            code = min(queue)
            ref = queue.pop(code)
            if code in seen:
                continue
            seen.add(code)
            slug = re.sub(r"([A-Z]+)(\d)", r"\1-\2", code).lower()
            url = f"{ORIGIN}/study/courses/{year}/{slug}/"
            source = None
            try:
                html, source = fetcher.fetch(url, year)
                course = parse_course(html, source, code)
                for rule in course["rules"].values():
                    from slop.rules import Rule

                    for dependency in sorted(references(Rule.model_validate(rule)) | set(
                        re.findall(CODE, rule.get("raw", ""))
                    )):
                        queue.setdefault(dependency.replace(" ", ""), {})
                courses.append(course)
                print(
                    f"{year} {code}: {course['title']} ({len(course['offerings'])} periods)",
                    flush=True,
                )
            except (httpx.HTTPStatusError, ValueError) as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code != 404:
                    raise
                courses.append(
                    {
                        "code": code,
                        "year": year,
                        "identity": code,
                        "title": ref.get("title", code),
                        "units": ref.get("units"),
                        "level": None,
                        "level_source": "UNKNOWN",
                        "overview": "",
                        "outcomes": [],
                        "assessments": [],
                        "exam": "UNKNOWN",
                        "elective": None,
                        "offerings": [],
                        "raw": {},
                        "rules": {
                            k: compile_requisite(k, None).model_dump()
                            for k in ["prerequisite", "corequisite", "antirequisite"]
                        },
                        "source": source
                        or {
                            "requested_url": url,
                            "canonical_url": url,
                            "year": year,
                            "fetched_at": datetime.now(UTC).isoformat(),
                            "sha256": hashlib.sha256(b"missing").hexdigest(),
                            "parser_version": PARSER_VERSION,
                        },
                        "verification": "UNKNOWN",
                        "source_status": "SOURCE_MISSING",
                        "parse_status": "UNPARSED",
                        "warnings": ["Official year-specific course page unavailable"],
                    }
                )
                print(f"{year} {code}: unavailable; retained UNKNOWN", flush=True)
    # Remove only exact, known course titles before parsing; never drop arbitrary prose.
    for course in courses:
        titles = {c["code"]: c["title"] for c in courses if c["year"] == course["year"]}
        for kind, raw in course["raw"].items():
            if raw is None:
                continue
            normalized = raw
            for code, title in sorted(titles.items(), key=lambda item: -len(item[1])):
                normalized = re.sub(
                    r"\b" + re.escape(code) + r"\s+" + re.escape(title) + r"(?=\s|$|[().,])",
                    code,
                    normalized,
                    flags=re.IGNORECASE,
                )
            rule = compile_requisite(kind, normalized)
            rule.raw = raw
            course["rules"][kind] = rule.model_dump()
        course["parse_status"] = "PARSED" if all(
            r["type"] != "UNKNOWN" for r in course["rules"].values()
        ) else "UNPARSED"
    for degree in degrees:
        required = set(degree["course_references"])
        relevant = [c for c in courses if c["year"] == degree["year"] and c["code"] in required]
        if any(
            c["verification"] != "VERIFIED"
            or any(r["type"] == "UNKNOWN" for r in c["rules"].values())
            for c in relevant
        ):
            degree["verification"] = "PARTIAL"
    payload = {"schema_version": 1, "degrees": degrees, "courses": courses, "relationships": []}
    output = Path(output)
    courses.sort(key=lambda course: (course["year"], course["code"]))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2))
    fetcher.prune()
    return payload


if __name__ == "__main__":
    ingest()
