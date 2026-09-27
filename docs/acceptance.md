# First-delivery acceptance ledger

This distinguishes software implementation from verified university data. No unknown source rule or future offering is treated as valid to make a demo pass.

| Journey / requirement | Implemented and checked | Remaining limitation |
| --- | --- | --- |
| 2026/2027 catalogue ingestion | Serial robots-aware ingestion; recursive course references; cached provenance, hashes; transactional idempotent loading; retained revisions | Fully verified catalogues are unavailable from the fetched sources. Missing/year-mismatched pages remain unknown. |
| Degree browsing | General BCOMP and all three linked majors, year switching, grouped requirements, course evidence/source inspection | AI/ML placeholder references require authoritative replacement; not hand-certified complete. |
| Local planner | Official suggested sequence, add/move/drag, statuses, locks, per-year IndexedDB persistence | Suggested future semesters are editable scaffolding, not proof of offerings. |
| Credits/waivers | Conditional provisional course credit and target prerequisite waivers; approved credit attempt status; repeats and failed/withdrawn attempts | Generic/partial external credit allocation is deferred. |
| Strict validation | AST-based satisfied/unsatisfied/unknown reports; conditional assumptions; exact failed-expression details | Unfamiliar prose requires maintainer review, never AI approval. |
| Fastest prerequisite path | CP-SAT considers AND/OR rules, known periods, loads, conflicts; returns earliest verified solution when optimality is proved | Many real paths cannot be proved within the current published horizon. |
| Remaining plan generation | Hard academic constraints; locked attempts; exam preferences; independent result validation before apply | No fully verified three-year BCOMP output can be produced from the current incomplete offerings. |
| Semantic elective search | BGE small English 384-dimensional vectors in pgvector; hybrid reciprocal-rank fusion; source evidence; degree-fit prioritization | Elective corpus is an initial CAD/design sample, not every university elective. |
| Natural-language routing | Deterministic degree/course/prerequisite/planner routes | Broad conversational comparison and career queries are deferred. |
| Automated tests | Parser goldens for both degree years and all majors, AST edge cases, graph/scheduling, API, real PostgreSQL/pgvector, local recovery, browser journeys | Historical browser versions and physical phones have not been tested. |
| Safety/public operations | Input limits, rate limiting, request IDs, stripped error reporting, privacy notice, no accounts/analytics | Production operators must configure their proxy and log retention; multiple replicas require shared limiting. |
| Deployment | Docker Compose, empty-database migration, readiness/health, environment examples, fixture/ingestion commands, Render/Cloudflare/Neon instructions, scheduled review artifact | Cloud resources have not been provisioned or published by this task. |
| Recovery | Validated versioned JSON export/import, review before replace | Browser clearing without export loses plans. |

The parser marks a recognized rule **VERIFIED** only for its deterministic structured translation. That label is not a claim that every related course, its historical equivalence, or the entire reference degree is fully verified. Catalogue-level status remains partial when required course data is unresolved.
