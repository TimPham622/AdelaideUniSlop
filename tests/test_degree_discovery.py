from pathlib import Path

from slop.degree_discovery import parse_degree_sitemap


def test_degree_sitemap_produces_draft_candidates_only():
    xml = Path("data/fixtures/html/degree-sitemap-excerpt.xml").read_text()
    result = parse_degree_sitemap(xml, 2027)
    assert {row["id"] for row in result["degrees"]} == {
        "bachelor-of-arts", "bachelor-of-science"
    }
    assert all(row["source_status"] == "DISCOVERED_UNVERIFIED"
               and row["program_code"] is None for row in result["degrees"])


def test_discovery_rejects_non_official_and_nested_links():
    xml = """<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://evil.example/study/degrees/fake/</loc></url>
      <url><loc>https://adelaide.edu.au/study/degrees/online/fake/</loc></url>
    </urlset>"""
    assert parse_degree_sitemap(xml, 2027)["degrees"] == []
