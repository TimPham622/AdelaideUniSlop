"""Extract only academic components from the private HTML cache for regression fixtures."""

import json
from pathlib import Path

from bs4 import BeautifulSoup
from slop.ingestion import parse_course, parse_degree

cache = Path(".cache/adelaide")
out = Path("data/fixtures/html")
for metadata in cache.glob("*.json"):
    source = json.loads(metadata.read_text())
    url = source["requested_url"]
    degree = (
        "/bachelor-of-computer-science" in url
        and "/degrees/" in url
        or any(
            url.endswith(f"/degrees/{year}/bachelor-of-computer-science/dom/")
            for year in [2026, 2027]
        )
    )
    course = url.endswith("/courses/2026/comp-1002/")
    if not (degree or course):
        continue
    soup = BeautifulSoup(metadata.with_suffix(".html").read_text(), "html.parser")
    if degree:
        nodes = [
            soup.find("h1"),
            soup.select_one(".cmp-course-info-by-year"),
            soup.select_one(".study-plan-future-students"),
        ]
        name = (
            f"degree-{source['year']}"
            + url.split("bachelor-of-computer-science")[1].split("/dom/")[0]
        )
    else:
        nodes = [soup.find("h1")]
        nodes.extend(soup.select(".course-details,.study-page-section"))
        name = "course-comp1002-2026"
    fragment = BeautifulSoup(
        "<main>" + "".join(str(n) for n in nodes if n) + "</main>", "html.parser"
    )
    for el in fragment.select("script,style,img,svg,button"):
        el.decompose()
    for el in fragment.find_all(True):
        for attr in list(el.attrs):
            if attr.startswith("on") or attr.startswith("data-") and attr != "data-course-type":
                del el.attrs[attr]
    html = str(fragment)
    (out / f"{name}.html").write_text(html)
    (out / f"{name}.source.json").write_text(json.dumps(source, indent=2))
    parsed = parse_degree(html, source) if degree else parse_course(html, source, "COMP1002")
    if degree:
        expected = {
            "summary_verified": parsed["summary_verified"],
            "total_units": parsed["total_units"],
            "groups": parsed["groups"],
            "standard_plan": parsed["standard_plan"],
        }
    else:
        expected = {k: parsed[k] for k in ["title", "raw", "rules", "outcomes", "assessments"]}
    (out / f"{name}.expected.json").write_text(json.dumps(expected, indent=2))
    print(name, [(g["id"], g["verification"], len(g["codes"])) for g in parsed.get("groups", [])])
