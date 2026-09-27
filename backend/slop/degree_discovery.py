"""Draft degree identities from Adelaide's public sitemap, never publish automatically."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

from slop.ingestion import ORIGIN, Fetcher

DEGREE_PATH = re.compile(r"^/study/degrees/([a-z0-9-]+)/?$")


def parse_degree_sitemap(xml: str, catalogue_year: int) -> dict:
    root = ElementTree.fromstring(xml)
    degrees = {}
    for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
        if not loc.text:
            continue
        parsed = urlparse(loc.text)
        match = DEGREE_PATH.fullmatch(parsed.path)
        if parsed.scheme != "https" or parsed.netloc != "adelaide.edu.au" or not match:
            continue
        slug = match[1]
        if slug in {"compare-degrees", "online"} or slug.isdigit() or parsed.query or parsed.fragment:
            continue
        degrees[slug] = {"id": slug, "canonical_url": f"{ORIGIN}{parsed.path.rstrip('/')}/",
                         "program_code": None, "title": None,
                         "source_status": "DISCOVERED_UNVERIFIED"}
    return {"schema_version": 1, "catalogue_year": catalogue_year,
            "source_url": f"{ORIGIN}/sitemap.xml",
            "source_sha256": hashlib.sha256(xml.encode()).hexdigest(),
            "degrees": sorted(degrees.values(), key=lambda row: row["id"])}


def discover_degrees(catalogue_year: int, output: Path) -> dict:
    if not 2020 <= catalogue_year <= 2100:
        raise ValueError("Unsupported catalogue year")
    fetcher = Fetcher()
    try:
        manifest = parse_degree_sitemap(fetcher.fetch_sitemap(), catalogue_year)
    finally:
        fetcher.client.close()
    manifest["discovered_at"] = datetime.now(UTC).isoformat()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest
