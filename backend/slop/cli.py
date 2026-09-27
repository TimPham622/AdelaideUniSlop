import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session

from slop.db import apply_overrides, catalogue, engine, import_catalogue


def main():
    parser = argparse.ArgumentParser(prog="slop")
    commands = parser.add_subparsers(dest="command", required=True)
    loader = commands.add_parser("load-fixtures")
    loader.add_argument("--file", type=Path, default=Path("data/fixtures/catalogue.json"))
    loader.add_argument("--dry-run", action="store_true")
    crawl = commands.add_parser("ingest")
    crawl.add_argument("--years", type=int, nargs="+", default=[2026, 2027])
    crawl.add_argument("--output", type=Path, default=Path("data/fixtures/catalogue.json"))
    commands.add_parser("embed")
    commands.add_parser("quality")
    upstream = commands.add_parser("import-upstream")
    upstream.add_argument("file", type=Path)
    upstream.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "ingest":
        from slop.ingestion import ingest

        ingest(args.years, args.output)
    elif args.command == "load-fixtures":
        payload = apply_overrides(json.loads(args.file.read_text()))
        if args.dry_run:
            print(
                f"{len(payload['degrees'])} degrees, {len(payload['courses'])} courses; no database writes"
            )
        else:
            with Session(engine) as session:
                print(import_catalogue(payload, session))
    elif args.command == "embed":
        from slop.search import embed_catalogue

        with Session(engine) as session:
            print(f"Embedded {embed_catalogue(session)} changed evidence chunks")
    elif args.command == "quality":
        with Session(engine) as session:
            data = catalogue(session)
        for year in sorted({d["year"] for d in data["degrees"]}):
            cs = [c for c in data["courses"] if c["year"] == year]
            print(
                json.dumps(
                    {
                        "year": year,
                        "courses": len(cs),
                        "with_offerings": sum(bool(c["offerings"]) for c in cs),
                        "unverified_versions": sum(c["verification"] != "VERIFIED" for c in cs),
                        "unparsed_rules": sum(
                            r["type"] == "UNKNOWN" for c in cs for r in c["rules"].values()
                        ),
                    }
                )
            )
    else:
        from slop.upstream import UpstreamCourse

        rows = json.loads(args.file.read_text())
        args.output.write_text(
            json.dumps([UpstreamCourse.model_validate(r).normalized() for r in rows], indent=2)
        )


if __name__ == "__main__":
    main()
