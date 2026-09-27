# adelaide uni slop

A React + TypeScript / FastAPI / PostgreSQL + pgvector degree planner for Adelaide University. Student plans stay in IndexedDB; server-side validation and generation are transient. There are no accounts, analytics, or student database. Generative AI is optional in the broader design and disabled in this release.

![Planner](docs/screenshots/planner-desktop.png)

## Run the complete application

```sh
docker compose up --build
```

Open **http://localhost:8081**. The API is at http://localhost:8000/docs. Compose creates PostgreSQL, applies migrations, loads the committed catalogue, embeds its evidence, and starts the web app. The first image build downloads the CPU embedding model. Subsequent starts use the model in the image. Ports bind to localhost; PostgreSQL data survives container restarts. Set `WEB_PORT` if port 8081 is already in use.

Use `docker compose down` to stop. Avoid `down -v` unless you intend to delete the catalogue database. Browser plans are independent of that database.

## What works

- Browse 2026 / 2027 Bachelor of Computer Science structures and three majors, with official source links and immutable source hashes.
- Load the official suggested sequence, add courses, drag cards, or use keyboard/touch period selectors. Track completed, current, planned, failed, withdrawn, and approved-credit attempts.
- Keep separate local plans for each catalogue year. Export/import strict, versioned JSON; review before replacing a saved plan.
- Evaluate typed rule trees using satisfied / unsatisfied / unknown states. Provisional credits and waivers remain conditional. Failed attempts grant no prerequisite credit; repeated attempts count units once.
- Explain prerequisite failures; check whether a course is takeable in a selected period; separately solve earliest prerequisite branches and remaining plans using OR-Tools CP-SAT over actual published offerings. Respect locked courses, load limits, and listed-exam preferences. Independently validate generated candidates before allowing application.
- Search the currently ingested course corpus by title, overview, learning outcome and assessment using BGE small English v1.5 embeddings plus lexical retrieval. Show evidence, selected-pathway requirement fit, and indexed coverage; search does not require a generative model.
- Route degree searches, course interests, prerequisite questions and planner questions without AI.
- Re-ingest live Adelaide sources through a rate-limited, robots-aware, cached CLI. Runtime requests use the local catalogue, not upstream websites.

## Source limitations: first-delivery acceptance is not yet complete

The software implements the first UI slice, **not all Phase A–H features**. The committed catalogue is real extracted data, not a fabricated demo curriculum. It is **not a fully verified degree catalogue**:

- Many year-qualified course URLs return a page labelled a different year. The importer preserves the requested year and marks those versions unknown; it does not reuse their offerings as verified information for that year.
- The source snapshot has no verified 2027 offerings and only a limited 2026 offering horizon. A complete three-year plan or many fastest paths cannot be certified from that data. The application returns an explanation instead of extrapolating recurring semesters.
- X-series codes such as `STATX100` and `ARTIX300` are official identifiers. `STATX100` is included in the AI/ML major’s 54-unit rule. Some course versions and future offerings remain unverified or year-mismatched, so this does not certify a complete study plan.
- Search covers only courses discovered from the Bachelor of Computer Science degree pages and their referenced rules. The currently indexed corpus is shown in the UI and is not presented as university-wide coverage.
- Some source requisite prose still requires reviewed overrides. A successful deterministic parse is distinct from verifying the entire degree.
- Degree search is limited to the reference Bachelor of Computer Science. Career exploration, comparison, accounts, PWA/offline installation, web administration and generative AI are outside this increment.

See [acceptance status](docs/acceptance.md) for the distinction between implemented behavior and unresolved source acceptance. The test catalogue used for solver proofs is synthetic and appears **only in tests**, never as university data in the app.

## Local development

Requires Node 22+, Python 3.12, [uv](https://docs.astral.sh/uv/), and PostgreSQL with pgvector. `.env.example` documents variables; export them into your shell when overriding defaults. The CLI does not automatically read `.env`.

```sh
docker compose up -d db
uv sync --frozen --extra dev --python 3.12
uv run alembic upgrade head
uv run slop load-fixtures
uv run slop embed
uv run uvicorn slop.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal:

```sh
npm ci --prefix apps/web
npm run dev --prefix apps/web
```

Open http://localhost:5173. Vite proxies `/api` to port 8000.

## Ingestion and publication

```sh
# Development cache TTL: one day. Raw private cache retention: fourteen days.
uv run slop ingest --years 2026 2027 --output data/fixtures/catalogue.json
uv run slop load-fixtures --dry-run
uv run slop load-fixtures
uv run slop embed
uv run slop quality
```

The initial degree URL and linked major pages seed discovery. The importer recursively fetches referenced prerequisites without query-specific course seeding. Requests are serial, at most one per second, with robots checks, conditional requests, retries, and `Retry-After`. It rejects arbitrary hosts and paths. Raw HTML lives only in ignored `.cache/adelaide`; sanitized academic fragments are committed for parser regression tests. Normalized data and provenance remain in Git and database revisions indefinitely.

Maintain [`compsci-adl/courses-api`](https://github.com/compsci-adl/courses-api) separately. The importer accepts JSON rows shaped like its raw `Course` ORM export, with `course_code`, raw requisite strings, `course_level`, and comma-separated `terms`; its reduced public detail response is insufficient for strict rule compilation. Normalize with `slop import-upstream input.json --output normalized-courses.json`, then review and merge course records into the catalogue before publication. Importing an upstream row alone leaves source verification unknown. Missing raw requisites become unknown; code-only requirement lists cannot certify logic. No runtime requests call courses-api.

Migration `0001` is frozen as the original schema; `0002` introduces degree identity and removes the one-degree-per-year limit. Active publication replaces course versions for included catalogue years while preserving historical revision payloads.

Publication is a Git workflow: inspect source changes and warnings, add reviewed overrides, run tests, and merge the normalized snapshot. A merged deployment loads that revision. Scheduled GitHub Actions produce a **review artifact**, not an automatically published catalogue. The default schedule is weekly; maintainers can run it manually or change the schedule during active development. Do not publish the raw HTML cache.

## Verification

```sh
uv run ruff check backend tests scripts
TEST_DATABASE_URL=postgresql+psycopg://slop:slop@localhost:5432/slop uv run pytest -q
npm run test --prefix apps/web
npm run build --prefix apps/web
cd apps/web
npx playwright install chromium firefox webkit
npm run test:e2e
```

Tests and CI never fetch the live university site. PostgreSQL tests use a disposable schema, without deleting your catalogue. Browser tests exercise Chromium, Firefox, WebKit, and mobile Safari emulation. Current engine builds have been tested; historical browser releases and physical iOS devices require a separate compatibility run.

CI uses lexical search and fixed test vectors, with no model download. Real BGE/pgvector retrieval is exercised by the local/Docker application. Production defaults to hybrid search after embedding; set `SEMANTIC_SEARCH=0` for an explicit lexical-only mode.

## Deployment and operations

- **Vendor-neutral:** the root Docker image exposes FastAPI, and `apps/web/Dockerfile` serves the static frontend through Nginx. The local frontend proxies `/api` to the backend.
- **Render:** use `render.yaml`. Set `DATABASE_URL` to a Neon or other PostgreSQL connection string with `sslmode=require`, and `CORS_ORIGINS` to the exact frontend origin. Provision pgvector and pg_trgm permissions. `/ready` checks database and catalogue; `/health` is process liveness. Migrations and fixture publication run at container startup.
- **Cloudflare Pages:** root `apps/web`, build `npm ci && npm run build`, output `dist`, Node 22. Set `VITE_API_URL` to the deployed API origin followed by `/api` before building. `_headers` and `_redirects` are included. Tighten the static CSP `connect-src` to that origin when provisioning it.
- **Neon:** the application normalizes PostgreSQL URLs to psycopg. It needs no GPU and no live upstream to answer requests.
- **Privacy:** disable platform body/query capture and analytics. Application access logging is disabled. Errors record only a generated request ID, exception class, and stack frame names/line numbers. Apply a short retention policy (for example seven days) to platform logs.
- **Rate limits:** one process maintains one-minute windows (30 expensive requests / 180 other API requests per connection IP). Multiple replicas need gateway/shared rate limiting. If using a trusted reverse proxy, configure trusted forwarded-IP handling there; never blindly trust public `X-Forwarded-For` headers. Without trusted forwarding, the conservative shared proxy limit still protects the server.
- **Recovery:** PostgreSQL holds only catalogue data and can be rebuilt from committed fixtures. Student recovery uses browser JSON export/import. There is no cloud student backup.

## Repository

| Location | Purpose |
| --- | --- |
| `apps/web/src` | React UI, strict import schema, IndexedDB storage |
| `backend/slop` | ingestion, rule compiler, validator/solver, search and API |
| `backend/migrations` | Alembic migrations |
| `data/fixtures` | normalized public catalogue and sanitized parser goldens |
| `data/rule_overrides` | reviewed source-hash-bound overrides |
| `tests` | deterministic parser, rule, planning, API and PostgreSQL tests |
| `docs/specification.md` | supplied full product specification |
| `docs/locked-decisions.md` | supplied first-delivery decisions, overriding conflicting scope |

The application name, workspace location and React/TypeScript stack follow the subsequent user decisions. The original documents retain their original wording for traceability.
