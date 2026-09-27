# Adelaide Degree Planner and Course Explorer
## Full Product and Engineering Specification

**Working name:** `Degreebook`  
**Primary users:** current and future Adelaide University students  
**Primary platform:** responsive web application / installable PWA  
**Student persistence:** browser-only via IndexedDB; no account system and no student database  
**Academic data:** Adelaide University degree/course pages plus `compsci-adl/courses-api`  
**Career data:** public occupation/skills datasets; no job-board or vacancy scraping  
**UI direction:** dense early-2010s social-network styling adapted for academic planning  
**Document date:** 27 September 2026

---

# 1. Product concept

Degreebook is an academic planning, degree-discovery and course-discovery tool for Adelaide University.

Its core purpose is to turn public university information into a structured academic model that can answer questions such as:

- What does this degree actually require?
- What have I completed and what is still missing?
- Can I take this course next study period?
- If not, what is the fastest verified prerequisite path?
- Which electives match an idea such as CAD, robotics, databases, climate modelling or computer graphics?
- Which matching electives can actually count toward my degree?
- Can the planner build the rest of my degree while respecting prerequisites and preferences?
- How do two degrees differ in structure, courses, entry requirements and career/skill coverage?
- Which degrees and courses relate to a career or skill area?

The centre of the product is a **strict degree planner**. Users choose the catalogue/program year that applies to them, choose a degree and any major/specialisation, enter completed/current/planned study, then edit the plan using drag-and-drop course cards. Degreebook continuously validates the plan.

The product also includes:

- degree and course profiles;
- degree logistics/admission information;
- natural-language search;
- semantic elective discovery;
- degree comparison;
- career → skill → course → degree exploration;
- prerequisite graph/pathing;
- preference-aware plan generation;
- credit and waiver modelling;
- source/evidence displays.

The early-2010s social-media influence is visual and navigational only. There are **no reviews, ratings, comments, profiles, discussion feeds, likes or community content**.

---

# 2. Goals and non-goals

## 2.1 Goals

| Goal | Meaning |
|---|---|
| **Strict academic planning** | Degree validity comes from a deterministic rules engine, not from an LLM guessing what university prose means. |
| **Current + future students** | Catalogue year is first-class. Historical/current/future program rules can coexist. |
| **Auditable recommendations** | A recommendation shows why it matched and which source text supports it. |
| **Interest-based elective search** | A phrase such as `CAD` can match course outcomes/topics even if the course title does not contain the term. |
| **Fast prerequisite pathing** | If a target course is blocked, show the earliest verified path through required prerequisites and offerings. |
| **Preference-aware generated plans** | Generate valid plans that can prefer no-listed-exam courses early, balanced assessments, interests, or early access to a target course. |
| **Low operating cost** | Core features work without a paid AI API. |
| **No account requirement** | Plans stay in IndexedDB and can be exported/imported. |
| **Source traceability** | Every important fact keeps catalogue year, source URL, fetch time and parse status. |
| **Graceful uncertainty** | The system may say `UNKNOWN` when a rule cannot be checked safely. |

## 2.2 Non-goals

| Out of scope | Reason |
|---|---|
| Student reviews/ratings/community content | Not required and adds moderation/identity concerns. |
| Class timetable builder | Course study-period availability matters; class times and clash detection do not. |
| Job-board scraping | Career exploration uses public skills/occupation datasets, not vacancies. |
| University-portal password scraping | The app should never request Adelaide University credentials. |
| Automatic credit approval | Credit/waivers are represented as official or assumed states, never issued by Degreebook. |
| AI deciding degree validity | AI can parse candidates or explain verified output, but cannot be the final academic rule evaluator. |
| Silent migration between catalogue years | A current student's applicable rules must not be replaced just because a newer catalogue exists. |

---

# 3. User groups

| User | Main need |
|---|---|
| Future undergraduate student | Explore degrees, entry requirements, majors, first-year study and careers. |
| Future postgraduate student | Understand prerequisites, structure and specialisations. |
| New student | Turn the official study plan into a personal plan. |
| Current student | Track completed/current/planned courses and remaining degree rules. |
| Student changing major | See which study still counts and what new requirements appear. |
| Student changing degree | Explore how existing courses could fit another program without claiming official credit. |
| Transfer/credit student | Model approved credit, proposed credit and prerequisite waivers correctly. |
| International student | See international entry, English, CRICOS/fees and study-mode information. |
| Part-time student | Generate a valid lower-load sequence around prerequisites. |
| Career explorer | Map occupations and skills into relevant degrees, majors and courses. |

---

# 4. Product principles

## 4.1 Deterministic first, AI second

Any answer with an academic consequence follows this pipeline:

```text
official source
    ↓
normalised data
    ↓
verified typed rule
    ↓
deterministic evaluator / solver
    ↓
human-readable explanation
```

AI is suitable for:

- natural-language intent detection;
- semantic embeddings;
- proposing a structured interpretation of unusual rule prose;
- plain-English explanations;
- comparison prose based on already-structured facts;
- mapping broad career/interests to skill concepts.

AI is not suitable for:

- silently deciding what an ambiguous prerequisite means;
- declaring a degree complete directly from prose;
- inventing course availability;
- treating proposed credit as approved;
- claiming an assessment has no exam when source data is incomplete.

## 4.2 Every result should be inspectable

A user should be able to determine:

- where a fact came from;
- which catalogue year it belongs to;
- which rule was applied;
- whether the rule is verified, provisional or unknown;
- why a course counts toward a requirement;
- why a course is blocked;
- which exact text caused a semantic match;
- which assumptions make a plan conditional.

## 4.3 Unknown is a valid answer

If a source rule cannot be represented safely:

> This requirement could not be checked automatically. The planner cannot confirm this part of the plan until the rule is verified.

That is preferable to a confident wrong answer.

---

# 5. Data sources

## 5.1 Adelaide University degree catalogue

Primary discovery stem:

```text
https://adelaide.edu.au/study/degrees/{catalogue_year}
```

Example supplied for this project:

```text
https://adelaide.edu.au/study/degrees/2027/bachelor-of-computer-science/dom/?student=future
```

Degree pages can expose:

- degree title;
- study level;
- domestic/international context;
- duration;
- campuses;
- study mode;
- start periods;
- program code;
- fees;
- SATAC/CRICOS identifiers where relevant;
- assumed knowledge;
- entry scores;
- English requirements;
- descriptive overview;
- key features;
- accreditation;
- career copy;
- majors/specialisations;
- degree structure;
- required unit totals;
- rule groups;
- standard study plans;
- course lists;
- elective groups;
- work-integrated-learning groups.

A current Bachelor of Computer Science page, for example, exposes the program code `BCOMP`, a 144-unit structure, majors, WIL requirements, electives and a standard study plan.

### URL handling

Store both:

```text
requested_url
canonical_url
catalogue_year
```

Do not infer catalogue year only from the final/canonical URL. The site may redirect or canonicalise a year-qualified page.

## 5.2 `compsci-adl/courses-api`

Repository:

```text
https://github.com/compsci-adl/courses-api
```

The existing project already provides a good course-data foundation. It uses FastAPI, SQLAlchemy, SQLite and BeautifulSoup.

Its course model includes fields such as:

- `course_id`;
- year;
- term(s);
- subject;
- course code;
- title;
- campus;
- study level;
- units;
- coordinator;
- course level;
- overview;
- raw prerequisite text;
- raw corequisite text;
- raw antirequisite text;
- university-wide-elective flag;
- source URL;
- course-outline URL;
- textbooks;
- learning outcomes;
- assessments.

The public course detail endpoint exposes learning outcomes, assessments and a parsed `requirements` object.

### Important limitation: requisite logic

The existing API's `parse_requisites()` extracts course-code-shaped values from raw requisite text. That is not enough for strict planning because it can lose structure such as:

```text
A AND B
A OR B
A AND (B OR C)
18 units of Level 2 study
permission of the course coordinator
```

Degreebook therefore needs the **raw prerequisite/corequisite/antirequisite strings** as inputs to its rule compiler.

### Important limitation: multi-year storage

The existing `Course` model has a `year` field, but `course_id` is marked unique. If an institutional course ID is reused across years, Degreebook should not use that schema as its long-term catalogue store.

Degreebook should maintain:

```text
stable course identity
    ├── 2026 course version
    ├── 2027 course version
    └── 2028 course version
```

## 5.3 Direct Adelaide course pages

Course pages are useful for:

- area/catalogue code;
- Course ID;
- unit value;
- level;
- campuses;
- owner/coordinator;
- WIL flag;
- university-wide-elective flag;
- overview;
- topics;
- learning outcomes;
- raw prerequisites/corequisites/antirequisites;
- assumed knowledge;
- assessments;
- study-period availability;
- degree membership.

This is especially useful for semantic search because the concept a user wants may appear only in learning outcomes or topics.

## 5.4 Career datasets

Do **not** scrape Seek, Indeed, LinkedIn Jobs, employer vacancies or similar sites.

Recommended public datasets:

### Jobs and Skills Australia

```text
https://www.jobsandskills.gov.au/data
https://www.jobsandskills.gov.au/data/occupation-and-industry-profiles
```

Use it for Australian occupation context and downloadable occupation data.

### O*NET

```text
https://www.onetcenter.org/database.html
```

O*NET provides machine-readable occupation data including skills, knowledge, tasks, work activities, technology skills and related occupations.

Use O*NET as a detailed skills/occupation taxonomy. Use Australian datasets for Australian employment context.

---

# 6. High-level architecture

Use a **modular monolith** rather than microservices.

```text
                         ┌─────────────────────────────┐
                         │ Adelaide degree/course     │
                         │ pages                      │
                         └──────────────┬──────────────┘
                                        │
┌──────────────────────┐                ▼
│ compsci-adl/         │       ┌────────────────────────────┐
│ courses-api          │──────▶│ Ingestion + normalisation  │
└──────────────────────┘       └──────────────┬─────────────┘
                                              │
                 ┌────────────────────────────┼─────────────────────────┐
                 │                            │                         │
                 ▼                            ▼                         ▼
        ┌─────────────────┐         ┌──────────────────┐      ┌────────────────┐
        │ PostgreSQL      │         │ Rule compiler + │      │ Search /       │
        │ + pgvector      │         │ evaluator        │      │ embeddings     │
        └────────┬────────┘         └────────┬─────────┘      └───────┬────────┘
                 │                            │                         │
                 └────────────────────────────┼─────────────────────────┘
                                              ▼
                                  ┌─────────────────────────┐
                                  │ FastAPI application     │
                                  │ catalogue               │
                                  │ planner + solver        │
                                  │ search                  │
                                  │ assistant router        │
                                  │ career explorer         │
                                  └────────────┬────────────┘
                                               │
                                               ▼
                                  ┌─────────────────────────┐
                                  │ Next.js web/PWA        │
                                  │ IndexedDB local plans  │
                                  │ no user accounts       │
                                  └─────────────────────────┘
```

### Why this shape

| Decision | Reason |
|---|---|
| One backend deployable | Low cost and lower operational overhead. |
| Internal modules | Clear boundaries without distributed-system complexity. |
| PostgreSQL | Good fit for versioned relational academic data. |
| pgvector | Semantic search without another database. |
| Postgres full-text/trigram search | Hybrid lexical search in the same store. |
| Background CLI/worker | Scraping and embedding builds do not need Kafka/Redis at this scale. |
| IndexedDB | Student plans remain in the browser. |
| Stateless planning endpoints | Server can calculate without persisting student plans. |

Do not begin with Redis, Kafka, Kubernetes or a separate vector database.

---

# 7. Recommended stack

| Area | Recommendation |
|---|---|
| Frontend | Next.js + TypeScript + React |
| Styling | CSS Modules or Tailwind |
| Drag/drop | dnd-kit |
| Client state | Zustand or normal React state |
| Local storage | IndexedDB through Dexie |
| Backend | Python FastAPI |
| ORM/migrations | SQLAlchemy + Alembic |
| Database | PostgreSQL |
| Vector search | pgvector |
| Lexical search | PostgreSQL full-text + trigram |
| Planner | Google OR-Tools CP-SAT |
| Parsing | BeautifulSoup/lxml |
| Dynamic fallback | Playwright only when static HTML is insufficient |
| Embeddings | small local sentence-transformer / ONNX model |
| Optional LLM | Ollama/llama.cpp or swappable cheap hosted provider |
| Tests | pytest + Vitest + Playwright |
| Local deployment | Docker Compose |

---

# 8. Suggested repository

```text
degreebook/
├── apps/
│   └── web/
│       ├── app/
│       ├── components/
│       ├── features/
│       │   ├── planner/
│       │   ├── degrees/
│       │   ├── courses/
│       │   ├── search/
│       │   ├── career/
│       │   └── compare/
│       └── lib/
├── backend/
│   ├── degreebook/
│   │   ├── api/
│   │   ├── catalogue/
│   │   ├── ingestion/
│   │   ├── rules/
│   │   ├── planner/
│   │   ├── search/
│   │   ├── assistant/
│   │   ├── career/
│   │   └── main.py
│   └── migrations/
├── data/
│   ├── fixtures/
│   ├── snapshots/
│   ├── rule_overrides/
│   └── career/
├── scripts/
├── tests/
├── docker-compose.yml
├── pyproject.toml
└── package.json
```

Keep `compsci-adl/courses-api` separate and consume it as an upstream source.

---

# 9. Catalogue-year model

Supporting current and future students requires versioning from day one.

Never store a degree as a timeless row.

```text
Degree identity
    ├── 2026 degree version
    ├── 2027 degree version
    └── 2028 degree version
```

Likewise:

```text
Course identity
    ├── 2026 course version
    ├── 2027 course version
    └── 2028 course version
```

Conceptual model:

```text
degree_identity
- id
- stable_slug
- program_code_if_stable

degree_version
- id
- degree_identity_id
- catalogue_year
- title
- source_url
- source_snapshot_id
- parser_version

course_identity
- id
- institutional_course_id
- canonical_code

course_version
- id
- course_identity_id
- catalogue_year
- title
- units
- overview
- requisites
- availability
```

Domestic/international fields should sit in audience-specific records so admissions/fees can differ without duplicating the whole academic structure when it is shared.

---

# 10. Degree crawler

## 10.1 Pipeline

```text
Seed /study/degrees/{year}
        ↓
Discover degree links
        ↓
Canonicalise URLs
        ↓
Fetch
        ↓
Store immutable raw snapshot
        ↓
Parse metadata
        ↓
Parse degree structure
        ↓
Parse study plan
        ↓
Discover majors/specialisations
        ↓
Resolve course references
        ↓
Compile academic rules
        ↓
Run quality checks
        ↓
Publish catalogue revision
```

## 10.2 Discovery

Primary method:

- crawl the year index;
- collect links matching degree-path patterns;
- follow linked major/specialisation variants;
- discover domestic/international forms;
- de-duplicate by canonical identity.

Do not rely only on guessed slugs.

## 10.3 Fetch policy

At run time:

- check current robots instructions;
- use a descriptive user-agent;
- limit concurrency;
- use a low request rate;
- cache responses;
- use `ETag`/`Last-Modified` where possible;
- respect `Retry-After`;
- retry transient failures;
- throttle/stop on repeated server errors.

The crawler is a catalogue mirror, not a load test.

## 10.4 Immutable source snapshots

Store:

```text
source_snapshot
- requested_url
- final_url
- catalogue_year
- fetched_at
- status_code
- content_type
- sha256
- body_storage_key
- etag
- last_modified
```

If source hash is unchanged, reparse only when parser version changed.

Benefits:

- regression tests;
- change detection;
- reprocessing without refetching;
- traceability;
- debugging after page-layout changes.

---

# 11. Degree parser

Split parsing by concept:

```text
parse_degree_page()
├── parse_identity()
├── parse_audience()
├── parse_logistics()
├── parse_admission()
├── parse_overview()
├── parse_accreditation()
├── parse_careers()
├── parse_degree_structure()
├── parse_standard_study_plan()
├── parse_course_groups()
└── parse_options()
```

Parser signal order:

1. semantic attributes/data attributes;
2. headings and nearby containers;
3. stable component classes;
4. table/header labels;
5. label/value text fallback.

Do not depend on one exact CSS layout.

Suggested parsed shape:

```yaml
degree:
  title:
  program_code:
  catalogue_year:
  study_level:
  duration:
  campuses: []
  study_modes: []
  start_periods: []
  audiences: []
  entry:
  identifiers:
  fees:
  overview:
  key_features: []
  accreditation: []
  careers: []
  structure_summary_raw:
  requirement_groups: []
  study_plan: []
  majors: []
  minors: []
  specialisations: []
  source:
```

Missing fields remain missing; do not fabricate them.

---

# 12. Course ingestion

Preferred order:

```text
courses-api has a trustworthy field
→ reuse it

needed field is missing/lossy
→ fetch official course page

sources disagree
→ retain provenance from both and flag QA
```

Do not write a second complete course scraper unless required.

## 12.1 Recommended upstream changes

If contributing to `courses-api` is possible:

1. expose raw requisite strings;
2. add a year bulk-export endpoint;
3. include source scrape timestamp/hash;
4. review `course_id` uniqueness for multi-year storage;
5. return structured term lists;
6. make timetable/class-list data optional in bulk export.

Example:

```http
GET /export/courses?year=2027
```

Example raw requirement extension:

```json
{
  "requirements_raw": {
    "prerequisites": "...",
    "corequisites": "...",
    "antirequisites": "..."
  }
}
```

---

# 13. Core database schema

## 13.1 Catalogue/provenance

```text
catalogue
- id UUID PK
- year INT
- status ENUM(draft, validating, published, failed)
- created_at
- published_at

source_document
- id UUID PK
- catalogue_id FK
- source_type
- requested_url
- canonical_url
- fetched_at
- sha256
- parser_version
- parse_status
```

## 13.2 Degrees

```text
degree
- id UUID PK
- stable_key
- program_code

degree_version
- id UUID PK
- degree_id FK
- catalogue_id FK
- title
- study_level
- duration_text
- overview
- structure_summary_raw
- source_document_id FK

degree_audience
- degree_version_id FK
- audience domestic|international
- fees_json
- entry_json
- english_json
- satac_code
- cricos_code
```

## 13.3 Degree options

```text
degree_option
- id
- degree_version_id
- type major|minor|specialisation|stream|discipline
- code
- title
- description
```

## 13.4 Courses

```text
course
- id
- stable_key
- institutional_course_id
- code

course_version
- id
- course_id
- catalogue_id
- title
- units
- level_of_study
- course_level
- campuses_json
- terms_json
- overview
- topics_json
- assumed_knowledge
- university_wide_elective
- wil
- source_document_id
```

## 13.5 Outcomes and assessments

```text
course_learning_outcome
- id
- course_version_id
- position
- text
- embedding

course_assessment
- id
- course_version_id
- title_raw
- weighting_raw
- weighting_numeric nullable
- hurdle_raw
- classification_json
```

Use `unknown` as a real assessment classification state.

## 13.6 Requirement groups

```text
requirement_group
- id
- degree_version_id
- degree_option_id nullable
- parent_group_id nullable
- title
- group_type
- raw_text
- rule_id
- display_order
```

## 13.7 Rule store

```text
academic_rule
- id
- entity_type
- entity_version_id
- rule_kind program|prerequisite|corequisite|antirequisite
- raw_text
- ast JSONB
- parse_method deterministic|llm_candidate|manual_override
- verification_status verified|provisional|unknown|rejected
- confidence nullable
- parser_version
- source_document_id
```

## 13.8 Career graph

```text
occupation
skill
occupation_skill
course_skill_match
occupation_mapping
```

Keep source system/code/version on every imported career record.

---

# 14. Rule AST

Rules should be typed trees, not strings.

Examples:

### Course

```json
{"type": "COURSE", "course": "COMP1002"}
```

### All

```json
{
  "type": "ALL",
  "children": [
    {"type": "COURSE", "course": "COMP1002"},
    {"type": "COURSE", "course": "COMP1003"}
  ]
}
```

### Either

```json
{
  "type": "ANY",
  "min_selected": 1,
  "children": [
    {"type": "COURSE", "course": "MATHxxxx"},
    {"type": "COURSE", "course": "STATxxxx"}
  ]
}
```

### Units from a group

```json
{
  "type": "MIN_UNITS",
  "units": 12,
  "scope": {
    "type": "GROUP",
    "group_id": "university-wide-electives"
  }
}
```

Suggested node set:

| Node | Use |
|---|---|
| `ALL` | all child rules |
| `ANY` | one/N child rules |
| `COURSE` | specific course |
| `COURSE_OR_EQUIVALENT` | course or approved equivalent |
| `MIN_UNITS` | minimum units |
| `MAX_UNITS` | maximum units |
| `EXACT_UNITS` | exact units |
| `UNIT_RANGE` | bounded units |
| `COURSE_SET` | selection from explicit courses |
| `GROUP` | referenced requirement group |
| `OPTION` | major/minor/specialisation |
| `LEVEL_FILTER` | course-level restriction |
| `SUBJECT_FILTER` | subject restriction |
| `WIL_FILTER` | WIL scope |
| `ELECTIVE_FILTER` | elective scope |
| `BEFORE` | prerequisite timing |
| `CONCURRENT_OR_BEFORE` | corequisite |
| `NOT` | antirequisite |
| `PERMISSION` | official permission needed |
| `UNKNOWN` | cannot encode safely |

The node set should grow from real source patterns, not from guessed complexity.

---

# 15. Rule parsing pipeline

Required behaviour:

> if a rule cannot be parsed confidently, mark it for manual verification and allow AI to propose a candidate parse.

Pipeline:

```text
raw rule text
     ↓
normalise
     ↓
deterministic grammar
     ├── complete → verified AST
     └── partial/fail
             ↓
       LLM candidate parser
             ↓
       JSON-schema validation
             ↓
       reference/logic checks
             ↓
       provisional candidate
             ↓
       manual override OR UNKNOWN
```

## 15.1 Deterministic parser

Common patterns:

- "must have completed X";
- "all of X/Y";
- "one of X/Y";
- AND/OR groups;
- N units from a scope;
- all/one of the following;
- must not have completed;
- permission/approval clauses.

Once patterns become non-trivial, use a grammar/parser generator such as Lark instead of a large regex pile.

## 15.2 AI candidate parser

Input is narrow:

```json
{
  "catalogue_year": 2027,
  "rule_kind": "prerequisite",
  "raw_text": "...",
  "known_course_codes": ["..."],
  "allowed_node_types": ["ALL", "ANY", "COURSE"]
}
```

Output must match a Pydantic schema.

## 15.3 Candidate checks

Before an AI candidate can be treated as useful:

- all referenced courses resolve or are explicitly unresolved;
- no unsupported node appears;
- no source clause disappears;
- no new factual clause appears;
- AND/OR structure remains faithful;
- antirequisite polarity is correct;
- manual/permission clauses remain manual/permission clauses.

If checks fail, keep the rule `UNKNOWN`.

## 15.4 Manual override store

```text
data/rule_overrides/{year}/courses/...
data/rule_overrides/{year}/degrees/...
```

Each override stores source hash. If the source hash changes, mark the override for review.

---

# 16. Validation states

Use more than valid/invalid.

| State | Meaning |
|---|---|
| **VALID** | All applicable verified rules pass. |
| **INVALID** | At least one verified rule fails. |
| **CONDITIONAL** | Plan works only if an explicit credit/waiver/permission assumption is accepted. |
| **UNKNOWN** | One or more applicable rules cannot be checked safely. |
| **STALE** | Relevant source/catalogue data could not be refreshed or is known stale. |

`CONDITIONAL` and `UNKNOWN` must not look like confirmed valid states.

---

# 17. Student plan data

All persistent student state is local.

Suggested IndexedDB records:

```text
planner_profile
- local_id
- catalogue_year
- degree_id
- degree_option_ids
- audience
- created_at
- updated_at

plan_item
- local_id
- course_id
- term_key
- status
- locked
- notes_optional

credit_item
- local_id
- credit_type
- course_equivalent
- units
- approval_status
- note_optional

planner_preferences
- pacing
- assessment_preferences
- interests
- target_courses
- target_careers
```

Export/import:

```text
degreebook-plan.json
```

The export includes schema version, catalogue context, plan state, credits and preferences.

---

# 18. Course states

Use explicit states:

```text
COMPLETED
CURRENT
PLANNED
CREDIT_APPROVED
CREDIT_PROPOSED
WAIVER_ASSUMED
FAILED_OR_RETAKE
REMOVED
```

`CREDIT_APPROVED`, `CREDIT_PROPOSED` and `WAIVER_ASSUMED` must behave differently.

---

# 19. Credit and waivers

## 19.1 Approved course-equivalent credit

Can potentially:

- satisfy a named course requirement;
- contribute relevant units;
- satisfy downstream prerequisites if the official decision treats it as equivalent.

## 19.2 Generic approved credit

Can potentially satisfy permitted unit/elective buckets but should not automatically satisfy a specific named prerequisite.

## 19.3 Proposed credit

User believes prior study may receive credit but it is unconfirmed.

Any plan depending on it becomes:

```text
CONDITIONAL
```

## 19.4 Prerequisite waiver

A waiver can conditionally unblock enrolment in a target course.

It does **not**:

- mark the prerequisite complete;
- grant its units;
- satisfy unrelated degree requirements.

UI wording:

> Conditional: this path assumes an approved prerequisite waiver. Degreebook cannot confirm that approval.

---

# 20. Planner UI

Desktop concept:

```text
┌──────────────────────────────────────────────────────────────────────────┐
│ Degreebook | Search degrees, courses, careers, rules...        Data ●  │
├────────────────┬──────────────────────────────────────┬─────────────────┤
│ MY DEGREE      │ Bachelor of Computer Science        │ DEGREE STATUS   │
│ Overview       │ Catalogue: 2027                     │ Validity        │
│ Planner        │                                      │ Requirements    │
│ Requirements   │ YEAR 1                              │ Remaining       │
│ Saved courses  │ ┌ Semester 1 ───┐ ┌ Semester 2 ───┐│ Warnings        │
│ Credits        │ │ course cards  │ │ course cards  ││                 │
│                │ └───────────────┘ └───────────────┘│                 │
│ EXPLORE        │ YEAR 2                              │                 │
│ Courses        │ ...                                  │                 │
│ Degrees        │                                      │                 │
│ Careers        │ + Add study period                   │                 │
│ Compare        │                                      │                 │
└────────────────┴──────────────────────────────────────┴─────────────────┘
```

A user can:

- drag courses between periods;
- lock a course/term;
- mark completed/current;
- add approved or proposed credit;
- add a waiver assumption;
- remove a planned course;
- create extra/non-standard periods.

After each edit:

```text
local edit
→ immediate structural UI update
→ debounced validation
→ inline diagnostics + status panel
```

Do not block invalid drag/drop. Let the user create a hypothetical invalid arrangement and explain the issue.

---

# 21. Requirement progress

The planner translates rule trees into readable progress.

Example:

```text
Core courses
✓ COMP1002
✓ COMP1003
○ COMP2017
...

Selected major
Artificial Intelligence and Machine Learning
...

Work integrated learning
○ ...

University-wide electives
Remaining: ...
```

Each requirement can expose:

```text
Why does this count?
Official source
Original rule wording
Rule verification status
```

The official standard study plan is a default suggestion, not the sole source of truth for degree validity.


---

# 22. Prerequisite graph and course eligibility

Build a directed prerequisite graph per catalogue year for visualisation and path search, but keep the rule AST as the authoritative representation because `OR` and nested logic cannot be represented correctly by a simple edge list.

Conceptually:

```text
COMP1002 ─────▶ COMP2001 ─────▶ COMP3001
      \                         /
       └──── alternative ──────┘
```

The visual graph is useful; the AST is what decides whether prerequisites are actually satisfied.

## 22.1 Eligibility function

Core domain operation:

```text
CanTake(course, study_period, student_state)
```

Check:

1. target course exists in the selected catalogue year;
2. course is offered in the requested study period;
3. verified prerequisite rule passes;
4. corequisite rule passes with same-period rules;
5. antirequisite rule passes;
6. permission/waiver rules are resolved or explicitly conditional;
7. course is not already completed unless repetition is valid;
8. required course data is not stale/unknown.

Return structure, not just text:

```json
{
  "status": "BLOCKED",
  "missing": ["COMPxxxx"],
  "conflicts": [],
  "unknown_rules": [],
  "conditional_assumptions": [],
  "next_possible_periods": ["..."],
  "source_rules": ["..."]
}
```

---

# 23. Fastest available prerequisite path

This is a core feature.

User:

```text
Can I take COMPxxxx next semester?
```

Possible result:

```text
No, not under the currently verified rules.

Fastest verified path

Semester 1
  COMP1xxx

Semester 2
  COMP2xxx

Semester 1 following year
  COMPxxxx

Reason
COMP2xxx requires COMP1xxx.
COMPxxxx requires COMP2xxx.
The required courses are only listed in the study periods shown.

Conditional alternative
A prerequisite waiver could change the path, but Degreebook treats it as conditional until the user records official approval.
```

## 23.1 Path algorithm

For a target course:

1. expand prerequisite AST;
2. mark already completed/approved equivalent prerequisites satisfied;
3. enumerate feasible `OR` branches;
4. remove antirequisite-conflicting branches;
5. map required courses to available study periods;
6. propagate earliest possible completion through dependencies;
7. compare feasible branches;
8. return the earliest verified branch;
9. return conditional branches separately if they depend on waivers/unknown rules.

Use graph search/dynamic programming for this subproblem. Use the full solver for whole-degree planning.

---

# 24. Study-period model

Do not hard-code only Semester 1 and Semester 2.

Model:

```text
study_period
- catalogue_year
- key
- display_name
- sequence_order
- start_date_optional
- end_date_optional
```

Possible source labels may include semester, trimester, summer, winter, online or other terms.

The planner can expose a preference:

```text
Include non-standard study periods? [Yes/No]
```

This prevents a generated plan from unexpectedly using a summer/online term.

---

# 25. Course availability

Timetable construction is out of scope, but study-period availability is required.

Model:

```text
course_offering
- course_version_id
- study_period_id
- campus
- mode
- source_status
```

Do not import individual lecture/tutorial meeting times into Degreebook unless timetable functionality is deliberately added later.

Availability affects:

- next-period eligibility;
- fastest prerequisite path;
- generated study plans;
- "can take now" search filtering.

---

# 26. Degree-rule evaluation

A degree check should return structured progress.

Example:

```json
{
  "degree_status": "INVALID",
  "requirements": [
    {
      "group": "core",
      "status": "PASS",
      "satisfied_by": ["..."]
    },
    {
      "group": "electives",
      "status": "FAIL",
      "remaining_units": 12,
      "eligible_candidates": ["..."]
    }
  ],
  "unknown_rules": [],
  "conditional_assumptions": []
}
```

The frontend should render the result rather than duplicate academic logic.

---

# 27. Avoiding accidental double counting

A strict degree engine must distinguish:

```text
course is eligible for a requirement
```

from:

```text
course has been allocated to satisfy that requirement
```

A course may appear valid for:

- a major bucket;
- a core option group;
- an elective bucket.

Whether it can satisfy multiple buckets at once depends on program rules.

Model allocation explicitly:

```text
requirement_allocation
- course_or_credit
- requirement_bucket
- units_allocated
```

If official rules are unclear on double counting, mark the result `UNKNOWN` or `CONDITIONAL` instead of inventing a policy.

---

# 28. Requirement allocation engine

For a fixed set of completed/planned courses:

1. build eligible course-to-requirement edges;
2. enforce compulsory-course groups;
3. enforce unit totals/ranges;
4. enforce known no-double-count rules;
5. allocate courses to maximise satisfied verified requirements;
6. return meaningful alternative allocations if ambiguous.

This can use the same solver infrastructure as plan generation.

---

# 29. Plan generation

User:

```text
Build the rest of my degree.
```

The generator must expose assumptions and preferences rather than output one mysterious schedule.

## 29.1 Hard constraints

Hard constraints cannot be violated in a `VALID` generated plan.

Examples:

- selected degree rules;
- required core courses;
- selected major/specialisation;
- unit requirements;
- prerequisite ordering;
- corequisites;
- antirequisites;
- study-period availability;
- completed courses fixed in the past;
- approved credit;
- locked planned courses;
- configured load limits;
- catalogue-year rules;
- unknown rules prevent a verified-valid result.

No timetable/class-time constraints are included.

## 29.2 Soft preferences

Possible settings:

```text
Assessment preference
○ No preference
○ Prefer no-listed-exam courses early
○ Balance listed-exam and non-exam courses
○ Prefer project/continuous assessment where possible

Pacing
○ Standard
○ Lighter
○ Finish as early as verified rules allow

Interests
[ CAD                         ]
[ robotics                    ]

Targets
[ COMPxxxx                    ]

Planning
☑ Preserve locked courses
☑ Avoid plans dependent on waivers
☑ Prefer courses that unlock relevant later courses
```

---

# 30. Assessment preference semantics

"Course has no exam" is too strong unless source data proves it.

Use classifications:

```text
CONFIRMED_EXAM
NO_LISTED_EXAM
UNKNOWN_ASSESSMENT
```

Recommended UI wording:

> Prefer courses with no listed exam in the available assessment data.

Assessment structures can change, so generated plans should always link to the official course page.

## 30.1 Assessment normalisation

Store raw first:

```text
title_raw
weighting_raw
hurdle_raw
learning_outcomes_raw
```

Derived classification:

```json
{
  "type": "exam|quiz|project|assignment|presentation|practical|portfolio|other|unknown",
  "is_exam": "yes|no|unknown",
  "is_group": "yes|no|unknown",
  "is_hurdle": "yes|no|unknown"
}
```

Use deterministic keywords first. AI may propose a class for unclear labels, but uncertain results stay `unknown`.

---

# 31. Constraint-solver model

OR-Tools CP-SAT is a good fit.

Example variables:

```text
x[course, period] ∈ {0,1}
selected_option[major] ∈ {0,1}
credit_used[credit, requirement] ∈ {0,1}
allocation[course, requirement] ∈ {0,1}
```

Possible hard constraints:

```text
required course appears
selected option rules pass
offering exists for selected period
prerequisites completed before target
corequisites completed before/same period
antirequisite exclusions hold
unit totals/ranges hold
locked course remains fixed
approved credits applied legally
```

Possible soft objectives:

```text
earlier_completion_penalty
exam_early_penalty
assessment_imbalance_penalty
interest_mismatch_penalty
conditional_waiver_penalty
unnecessary_course_penalty
unlock_value_bonus
```

Use explicit objective weights/configuration. Do not let an LLM arrange the plan.

---

# 32. Generated-plan alternatives

When possible, return materially different options:

```text
Plan A — Earliest verified completion
Plan B — Fewer listed exams early
Plan C — Interest-weighted electives
```

These are strategy labels, not "best/worst" judgments.

Each plan should show:

- validity state;
- assumptions;
- unknown rules;
- selected soft preferences;
- why major course placements were made.

---

# 33. Solver diagnostics

Bad:

```text
No solution found.
```

Better:

```text
No verified plan satisfies the selected constraints.

Conflict:
- COMP3xxx is locked to Semester 1.
- COMP2xxx must be completed first.
- COMP2xxx is only listed in Semester 2 before that point.

Possible resolution:
- move COMP3xxx later;
- remove the lock;
- add a conditional waiver assumption if official approval may be available.
```

For complex failures, calculate a minimal or near-minimal conflict set.

---

# 34. "Why here?" explanations

Every solver-generated placement should have:

```text
Why here?
```

Example:

```text
- This course is listed in Semester 2.
- Its prerequisite is completed in Semester 1.
- It satisfies your selected major.
- Among otherwise valid choices, this plan preferred courses with no listed exam early.
```

The first items are hard facts; the last is a soft preference explanation.

---

# 35. Assessment-balance mode

If a user selects:

```text
I want a good mix between exam and no-exam courses.
```

The solver should:

- use known assessment classifications only;
- spread known exam-heavy courses where alternatives exist;
- treat unknown assessment data as unknown, not no-exam;
- preserve hard academic constraints.

Do not infer course difficulty from assessment type.

---

# 36. "No exams at the start" mode

Make this a soft preference by default.

UI:

```text
Avoid courses with listed exams in early study periods
Strength:
[Prefer] [Strongly prefer]
```

If a user chooses an absolute constraint and the degree cannot satisfy it, return a conflict explanation rather than silently breaking the constraint.

---

# 37. Plan branches

Local storage makes scenario planning easy.

Example:

```text
My plan
├── AI major
├── Programming Languages major
└── Lighter Year 2
```

Each branch keeps:

- catalogue year;
- degree;
- options;
- course placements;
- credits/waivers;
- preferences.

Users can clone rather than overwrite a plan.

---

# 38. Compare plan branches

Example comparison:

| Dimension | Branch A | Branch B |
|---|---|---|
| Validation state | ... | ... |
| Final study period | ... | ... |
| Major | ... | ... |
| Known assessment mix | ... | ... |
| Interest alignment | ... | ... |
| Conditional waivers | ... | ... |
| Unknown rules | ... | ... |

Do not collapse plan comparison to a single overall score.

---

# 39. Semantic elective discovery

Example user query:

```text
I want an elective focused on CAD.
```

Search across:

- course title;
- overview;
- listed topics;
- learning outcomes;
- assessment text where useful;
- discipline/subject;
- skill tags.

## 39.1 Retrieval pipeline

```text
query
  ├── lexical retrieval
  ├── semantic embedding retrieval
  └── skill/alias expansion
           ↓
       candidate merge
           ↓
     degree-fit checks
           ↓
 prerequisite eligibility
           ↓
   evidence extraction
           ↓
        ranking
```

## 39.2 Ranking signals

Conceptually:

```text
retrieval relevance
+ verified degree compatibility
+ current prerequisite feasibility
+ period availability
+ interest alignment
+ career-skill alignment
- unknown-rule penalty
- prerequisite-distance penalty
```

Default behaviour:

```text
All Adelaide courses
Sort: Best match for my degree
[✓] Prioritise courses that can count toward my degree
[ ] Only show courses I can currently take
```

This satisfies the requirement to show both broad results and degree-compatible results while prioritising the latter.

---

# 40. Semantic-search evidence

Every result should explain why it matched.

Example:

```text
Course: Mechanical Design ...

Why it matched
• Learning outcome: "...computer-aided design..."
• Topic: "3D solid modelling"

For your degree
✓ Eligible university-wide elective
✓ Verified prerequisites satisfied
Offered
Semester 2

Source
Official Adelaide course page
```

If the match is conceptual rather than exact, label it:

```text
Semantic match
```

Never ask an LLM to invent evidence text.

---

# 41. Embedding design

Create separate chunks for:

```text
course title
course overview
each learning outcome
topic groups
assessment summary
degree overview
major description
career description
skill description
```

Separate chunks allow exact evidence retrieval.

Store:

```text
entity_type
entity_id
field
position
text
source_document_id
embedding
embedding_model_version
```

Use a small open embedding model runnable on CPU/ONNX.

Precompute catalogue embeddings at ingestion time. Only user queries need live embedding work.

---

# 42. Hybrid search

Do not use vector search alone.

## 42.1 Lexical side

Use PostgreSQL:

- exact course-code matching;
- title matching;
- trigram/fuzzy matching;
- `tsvector` full-text search;
- alias expansion.

Priority:

```text
exact code
> exact title
> title prefix
> lexical content
> semantic-only
```

## 42.2 Semantic side

Use pgvector.

For an Adelaide-sized dataset, begin with simple vector similarity and add approximate indexing only if measurements justify it.

## 42.3 Merge

Reciprocal-rank fusion is a simple and inspectable way to combine lexical and semantic rankings.

Keep component ranks in developer diagnostics.

---

# 43. Search aliases and skill concepts

Maintain a controlled alias/concept layer.

Example:

```text
CAD
→ computer-aided design
→ 3D CAD
→ solid modelling
→ engineering drawing
```

Other examples:

```text
AI → artificial intelligence
ML → machine learning
HCI → human-computer interaction
DB → database
```

Sources can include public skill taxonomies and reviewed technical abbreviations.

Do not make unreviewed LLM-generated aliases permanent catalogue truth.

---

# 44. Search result types

The one search box can return:

```text
DEGREE
COURSE
CAREER
RULE/HELP
PLANNER ACTION
```

Course card:

```text
[COURSE] COMPxxxx — Title

Matched:
CAD · 3D modelling

Evidence:
Learning outcome 2: "..."

For your plan:
✓ Can count as an elective
○ Not currently eligible
Missing: COMPyyyy

[View] [Show path] [Add to plan]
```

Degree card:

```text
[DEGREE] Bachelor of ...

Matched:
programming · AI

Evidence:
major/course structure...
```

Career card:

```text
[CAREER] Occupation

Matched skills:
...
```

---

# 45. Search filters

Useful filters:

```text
Catalogue year
Study level
Course level
Subject
Campus
Study period
University-wide elective
WIL
Degree-compatible
Currently eligible
No listed exam
Assessment data known
Major/specialisation
Units
```

Keep "no listed exam" distinct from a claim of permanently exam-free.

---

# 46. One global natural-language search bar

Examples:

```text
degrees involving programming but not much physics

I want an elective involving CAD

can I take COMPxxxx next semester?

what is the difference between computer science and software engineering?

build the rest of my degree with fewer exams early

why is this course blocked?

I want to work in robotics

courses that teach database security
```

Supported intent types:

```text
DEGREE_SEARCH
COURSE_SEARCH
SEMANTIC_ELECTIVE_SEARCH
COURSE_ELIGIBILITY
PREREQUISITE_PATH
PLAN_VALIDATE
PLAN_GENERATE
RULE_EXPLAIN
DEGREE_COMPARE
CAREER_EXPLORE
NAVIGATION
UNKNOWN
```

---

# 47. Intent routing

Route without AI where possible.

Examples:

- exact course code → course lookup;
- `can I take ...` → eligibility;
- `compare X and Y` → comparison;
- broad concept phrase → semantic search.

Optional LLM output must be structured:

```json
{
  "intent": "COURSE_ELIGIBILITY",
  "course_code": "COMPxxxx",
  "study_period": "next",
  "constraints": [],
  "confidence": 0.97
}
```

The router does not answer the academic question. It dispatches to the deterministic domain service.

---

# 48. Low-cost AI architecture

The application should remain useful with generative AI disabled.

## 48.1 Tier 0: no generative model

Still available:

- degree browsing;
- strict validation;
- prerequisite paths;
- generated plans;
- lexical search;
- semantic embeddings;
- evidence cards;
- career matching;
- template explanations.

## 48.2 Tier 1: local model

Optional through:

```text
Ollama
or
llama.cpp
```

Use a small instruct model appropriate for the machine.

Tasks:

- intent extraction;
- candidate rule parsing;
- natural explanation;
- sourced comparison prose.

## 48.3 Tier 2: hosted free/cheap provider

Hide behind an adapter.

```python
class LLMProvider:
    async def structured(...): ...
    async def explain(...): ...
```

Do not hard-code current free-tier pricing because it changes.

## 48.4 Failure behaviour

If the model is unavailable:

```text
validation still works
planner still works
semantic search still works
career explorer still works
degree/course browsing still works
```

Only flexible language interpretation/explanation degrades.

---

# 49. Explanation engine

Never ask:

```text
Here is the student's entire degree. Is it valid?
```

Instead generate a deterministic result:

```json
{
  "status": "INVALID",
  "checks": [
    {
      "type": "MISSING_PREREQUISITE",
      "target": "COMPxxxx",
      "missing": ["COMPyyyy"],
      "source_rule": "..."
    }
  ]
}
```

Then render it through templates or an optional LLM.

Template:

```text
COMPxxxx is blocked because COMPyyyy must be completed first.
```

The LLM may rephrase but cannot change the facts.

---

# 50. Degree comparison

Compare factual categories:

| Category | Example |
|---|---|
| Structure | unit total, required groups, electives, WIL |
| Duration/mode | duration, full/part-time |
| Location | campuses |
| Admission | entry requirements, assumed knowledge |
| Curriculum | required subjects and options |
| Majors | available specialisations |
| Assessment profile | only where source course data supports aggregation |
| Careers | university-listed outcomes plus external skill links |
| Flexibility | elective/choice space |
| Professional status | accreditation/membership claims from official source |
| Prerequisite shape | verified dependency depth |

For semantic statements such as "more programming-focused", show the basis:

> Estimated from required-course outcomes/topics in the selected catalogue.

Do not present semantic ranking as an official university classification.

---

# 51. Degree logistics/profile page

Possible tabs:

```text
[Overview] [Study Plan] [Requirements] [Courses] [Entry] [Careers] [Info]
```

Show:

- program code;
- catalogue year;
- level;
- duration;
- campus;
- study mode;
- start periods;
- domestic/international selector;
- entry requirements;
- assumed knowledge;
- English requirements;
- fees text;
- SATAC/CRICOS where relevant;
- accreditation;
- careers;
- majors/specialisations;
- source freshness.

Every relevant panel can expose:

```text
Official source ↗
Catalogue: 2027
Last checked: ...
```

---

# 52. Career explorer

The career explorer is not a job search engine.

Graph:

```text
occupation
    ↓
skills / knowledge / activities
    ↓
course outcomes/topics
    ↓
degree requirement membership
    ↓
degree / major
```

Career page:

```text
Occupation: Software Engineer

What this occupation involves
[source]

Skills/knowledge
• ...
• ...

Adelaide matches

Courses
• COMP...
  Evidence: learning outcome ...

Degrees
• ...
  Required-course match
  Major match
  Elective-only match
```

---

# 53. Career matching

For each occupation:

1. import skill/knowledge/task concepts;
2. create/reuse skill vectors;
3. compare them with course chunks;
4. retain evidence sentences;
5. aggregate course matches into major/degree matches;
6. distinguish required-course matches from optional elective matches;
7. label every source.

Use wording such as:

```text
Skill alignment
```

not:

```text
Guaranteed career outcome
```

---

# 54. Career data separation

Use source labels:

```text
UNIVERSITY_LISTED
EXTERNAL_SKILL_MATCH
USER_INTEREST_MATCH
```

Example UI:

```text
Listed by Adelaide University
```

versus:

```text
Related by Degreebook skill match
```

Do not imply university endorsement of external mappings.

---

# 55. Occupation data ingestion

Suggested modules:

```text
career/
├── jsa.py
├── onet.py
├── mappings.py
├── matcher.py
└── service.py
```

Store source release/version.

Because Australian and O*NET classifications differ, use explicit mapping records rather than assuming codes correspond.

```text
occupation_mapping
- from_system
- from_code
- to_system
- to_code
- mapping_type
- source/confidence
```

---

# 56. Current-student mode

Setup:

```text
Which catalogue/program structure applies to you?
[Year]

Degree
[...]

Major/specialisation
[...]

Completed/current study
[Search] [Paste course codes]

Approved or proposed credit
[Add]
```

Do not imply that the current calendar year is automatically the student's governing catalogue year.

---

# 57. Future-student mode

Prioritise:

- degree discovery;
- entry requirements;
- majors;
- first-year/standard study plan;
- degree structure;
- elective flexibility;
- career mapping;
- comparison;
- semantic topic search.

Future students can build hypothetical plans with no completed-course state.

---

# 58. Degree-transfer exploration

A user may compare:

```text
From: Degree A / year
To: Degree B / year
```

Classify completed courses as:

```text
directly listed in destination requirements
potential elective fit
not visibly applicable
requires official credit/rule decision
```

Call the feature:

```text
Transfer exploration
```

not guaranteed credit transfer.

---

# 59. Plan/source provenance

Each plan references:

```text
catalogue year
published catalogue revision
degree version
```

If a new revision appears:

```text
Catalogue data changed since this plan was last validated.
[Revalidate]
[View data changes]
```

Never silently move an older plan to a newer catalogue year.

---

# 60. Source freshness and stale states

If a refresh fails:

```text
Data warning
This page was last successfully checked on [date].
The latest refresh failed.
```

Keep the last known data.

If a source changes and the new rule fails to parse:

```text
previous rule: verified
new source: changed
new rule: unknown/provisional
```

The affected degree/course should show the new uncertainty instead of quietly retaining an old rule as if nothing changed.


---

# 61. Change detection

Internal change detection makes the crawler maintainable.

Compare:

- source hash;
- parsed field values;
- rule AST;
- degree-course membership;
- standard study-plan placements;
- assessment structures;
- course offerings.

Generate diffs such as:

```text
BCOMP / 2027

Changed:
- requirement group wording
- COMPxxxx added to core
- elective group unit range changed
- major option renamed
```

If a manual rule override points at changed source text, mark it for review.

---

# 62. Data-quality pipeline

Every ingestion run should generate a report.

Suggested counts:

```text
degree pages discovered
degree pages fetched
degree pages parsed
course references resolved
course references unresolved
degree rules compiled
course requisite rules compiled
verified rules
provisional rules
unknown rules
changed source documents
parser failures
duplicate identities
```

Use publication gates. A new catalogue revision should not become active if a site redesign causes widespread parser failure.

Exact thresholds should come from observed data rather than arbitrary assumptions.

---

# 63. Staged catalogue publication

Do not mutate the live catalogue during a crawl.

Use:

```text
crawl
→ draft snapshot
→ parse
→ compile rules
→ build search index
→ quality checks
→ manual review if needed
→ publish revision
```

Only the final published revision is exposed as the default API snapshot.

This prevents users seeing half-scraped data.

---

# 64. Parser fixture tests

Keep representative source snapshots under test fixtures.

Cover:

- simple degree;
- degree with majors;
- honours;
- postgraduate;
- domestic;
- international;
- nested elective rules;
- unit ranges;
- optional groups;
- missing sections;
- unusual course codes;
- source-layout variants.

Tests assert structured parsed output.

Do not hit the live university site during normal unit tests.

---

# 65. Golden rule tests

For reviewed rules:

```text
raw source text
→ expected AST
```

If a parser change alters the AST, the test shows exactly which academic meaning changed.

Examples should include:

```text
A and B
A or B
A and (B or C)
N units from group
one major from list
must not have completed X
permission clause
```

---

# 66. Synthetic planner tests

Build small fake catalogues that are easy to reason about.

Example:

```text
A offered S1
B requires A, offered S2
C requires B, offered S1
D requires A OR X
```

Test:

- earliest path;
- same-term prerequisite failure;
- OR branches;
- corequisites;
- antirequisites;
- unavailable periods;
- locked-course conflicts;
- approved/proposed credit;
- waiver assumptions;
- degree-unit constraints;
- double-count allocation.

Synthetic cases catch domain bugs more clearly than relying only on real catalogue data.

---

# 67. Rule-evaluator invariants

Useful property tests:

- adding an irrelevant completed course cannot make a satisfied `ALL` rule fail;
- satisfying an allowed branch of `ANY` satisfies that node;
- an antirequisite conflict remains a conflict when more courses are added;
- proposed credit cannot turn `CONDITIONAL` into verified `VALID`;
- approved specific equivalence behaves consistently;
- unknown child rules propagate using defined state logic;
- a course cannot be allocated twice when a no-double-count rule applies.

---

# 68. Search relevance tests

Create a reviewed benchmark.

Example:

```text
Query: CAD
Relevant concepts:
- computer-aided design
- solid modelling
- 3D modelling

Query: databases
Relevant:
- relational database
- SQL
- data modelling
- database security
```

Evaluate:

- lexical-only;
- semantic-only;
- hybrid;
- hybrid + degree fit.

Store expected top/relevant entities and evidence chunks.

---

# 69. AI rule-parser evaluation

Build a corpus of raw rules with reviewed ASTs.

Measure:

- structural match;
- course-reference accuracy;
- AND/OR preservation;
- omitted-clause rate;
- invented-clause rate;
- automatically accepted percentage;
- manual-review percentage.

The objective is safe automation, not maximum automatic acceptance.

---

# 70. Course identity normalisation

Build one canonical course-code parser.

Possible source forms:

```text
COMP1002
COMP 1002
comp-1002
```

Canonical:

```text
COMP1002
```

Keep:

```text
subject
number
suffix_if_present
raw_code
canonical_code
```

Do not assume every subject prefix is a single word unless the source data proves it.

---

# 71. Degree-page/course reconciliation

Degree pages may refer to courses in different formats from `courses-api`.

Resolution:

```text
raw degree reference
→ code normalisation
→ exact version match
→ institutional ID match if available
→ unresolved reference if still ambiguous
```

Never silently discard an unresolved course.

Store:

```text
unresolved_course_reference
- raw_code
- degree_version
- requirement_group
- source_document
```

---

# 72. Source-conflict handling

Example conflict:

```text
Degree page lists COMPxxxx as required.
Course source has no verified offering for the selected catalogue year.
```

Show:

> The course is listed in the degree structure, but the available course data could not confirm an offering for the selected year.

Flag internally.

Use fact-specific source priority:

| Fact | Primary source |
|---|---|
| Degree membership | degree structure page |
| Course prerequisite | course page/raw course source |
| Standard placement | degree study plan |
| Offering/study period | course availability source |
| Entry requirement | audience-specific degree page |

Do not create one blanket "source A always wins" rule.

---

# 73. Data provenance UI

Normal display:

```text
Source: Adelaide University
Catalogue: 2027
Last checked: ...
```

Expanded developer/trust display:

```text
Requested URL
Canonical URL
Source hash
Parser version
Rule parse method
Verification status
Original rule wording
```

This is valuable when an academic rule is disputed or unclear.

---

# 74. 2010s social-media-inspired UI

The visual goal is a dense academic workspace that feels like a 2010-era social-network/product dashboard without copying one site exactly.

Use:

- fixed top navigation;
- dark/medium blue header;
- grey/off-white page chrome;
- bordered panels;
- small metadata labels;
- compact tabs;
- left rail navigation;
- centre content;
- optional right status rail;
- obvious text links;
- square or mildly rounded corners;
- restrained shadows;
- dense tables.

Avoid:

- huge hero sections;
- oversized cards;
- extreme whitespace;
- glass effects;
- giant rounded pills;
- engagement mechanics.

The interface should feel like an information system, not a marketing page.

---

# 75. Accessibility

The nostalgic look cannot reduce accessibility.

Require:

- WCAG-compatible contrast;
- visible focus;
- complete keyboard navigation;
- keyboard alternative to drag/drop;
- semantic headings;
- screen-reader labels;
- reduced-motion setting;
- status icons/text in addition to colour;
- touch-friendly course move controls on mobile.

---

# 76. Desktop layout

Concept:

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ Degreebook | Search... | My Degree | Explore | Compare | Data           │
├───────────────┬───────────────────────────────────────┬───────────────────┤
│ Left rail     │ Main                                 │ Right rail        │
│               │                                      │                   │
│ Overview      │ Degree profile / planner / results  │ Degree status     │
│ Planner       │                                      │ Remaining rules   │
│ Requirements  │                                      │ Warnings          │
│ Saved courses │                                      │ Source health     │
│ Credits       │                                      │                   │
├───────────────┴───────────────────────────────────────┴───────────────────┤
│ compact footer / source links                                             │
└───────────────────────────────────────────────────────────────────────────┘
```

---

# 77. Mobile layout

Collapse into:

```text
top bar
main content
drawer/bottom navigation
status drawer
```

For drag/drop, offer:

```text
Move course
→ choose study period
```

so planning remains usable without drag gestures.

---

# 78. Main screens

## Home

```text
Search degrees, courses, careers, skills...
[                                                     ]

Browse
[Degrees] [Courses] [Careers]

Start a plan
Catalogue year: [...]
Degree: [...]

Examples
"Find me an elective about CAD"
"Can I take COMPxxxx next semester?"
"Compare Computer Science and Software Engineering"
"I want to work in robotics"
```

## My Degree

Show:

- selected degree/year;
- major/specialisation;
- validation state;
- progress;
- remaining rule groups;
- warnings;
- official-source links.

## Planner

Drag/drop study periods plus generator controls.

## Requirements

Readable tree/checklist of compiled rules.

## Course

Overview/requisites/outcomes/assessment/availability/degree fit.

## Electives

Semantic search with planner-aware compatibility.

## Compare

Degree comparison table plus sourced explanation.

## Careers

Occupation → skill → course → degree.

## Data

Catalogue freshness and source information.

---

# 79. Course page

Suggested layout:

```text
COMPxxxx — Course title
Undergraduate · 6 units · Catalogue 2027

[Add to plan] [Find earliest path] [Official page ↗]

Overview
...

Topics
...

Learning outcomes
1. ...
2. ...

Requisites
[tree]

Assessment
...

Availability
...

Your degree
✓ Can count toward ...
! Missing prerequisite ...
```

Tabs:

```text
[Overview] [Requirements] [Outcomes] [Assessment] [Availability] [Degree Fit]
```

---

# 80. Rule visualisation

Example:

```text
Prerequisite

ALL
├─ COMP1002
└─ ONE OF
   ├─ MATHxxxx
   └─ STATxxxx
```

Unit group:

```text
Complete at least [N] units from
└─ University-wide electives
```

Include:

```text
[View original source wording]
```

This is particularly important for AI-assisted candidate parses.

---

# 81. Degree profile

Tabs:

```text
[Overview] [Study Plan] [Requirements] [Courses] [Entry] [Careers] [Info]
```

Information can include:

- program code;
- catalogue year;
- duration;
- campuses;
- mode;
- intakes;
- degree overview;
- majors/specialisations;
- entry scores/prerequisites;
- assumed knowledge;
- English requirements;
- SATAC/CRICOS;
- fees text;
- accreditation;
- careers;
- source date.

The page should feel like an old "profile" page, but for a degree.

---

# 82. Search result evidence design

Course result:

```text
[COURSE] COMPxxxx — Title

Why it matched
• Learning outcome: "..."
• Related concept: CAD / solid modelling

Degree fit
✓ Eligible elective

Eligibility
○ Available after COMPyyyy

[View] [Show path] [Add]
```

If the source evidence is a semantic match rather than an exact word, say so.

Do not display generated text in quotation marks as though it were source text.

---

# 83. Degree search

Future-student query:

```text
I want programming and AI but not much physics.
```

Search across:

- degree overview;
- major descriptions;
- required courses;
- required-course outcomes;
- discipline/subject composition;
- career skill graph.

A safe explanation might say:

```text
Matched:
- programming-related required courses
- an AI/ML major option

Physics:
- no physics course was found among the indexed core-course set in this catalogue snapshot.
```

Avoid a stronger statement such as:

```text
This degree has no physics.
```

unless the structure truly proves it.

---

# 84. Current-plan search context

Search behaves differently by context.

| Context | Behaviour |
|---|---|
| No degree selected | Rank by query relevance. |
| Degree selected | Prefer courses compatible with the degree. |
| Active plan | Prefer degree fit + current prerequisite eligibility + remaining rule needs. |

This makes the same search bar useful before and after a student creates a plan.

---

# 85. Degree-fit classification

Given a course and selected degree:

```text
REQUIRED
OPTION
ELIGIBLE_ELECTIVE
ELIGIBLE_MULTIPLE_BUCKETS
NOT_APPLICABLE
UNKNOWN
```

Example:

```json
{
  "fit": "ELIGIBLE_MULTIPLE_BUCKETS",
  "buckets": [
    "major-choice",
    "university-wide-elective"
  ],
  "note": "Final allocation affects remaining requirements."
}
```

---

# 86. Saved courses

A local shortlist allows a student to save courses found through:

- elective search;
- career explorer;
- degree comparison.

Card:

```text
COMPxxxx
CAD / design match
Eligible elective
Missing prerequisite: COMPyyyy
```

No cloud storage is required.

---

# 87. Interest profile

Local-only preference:

```text
interests:
- CAD
- robotics
- embedded programming
```

Use these as semantic inputs to elective ranking and plan generation.

Do not build a cross-user behavioural profile.

---

# 88. Career preference

Local-only:

```text
target careers:
- Software Engineer
- Robotics Engineer
```

When a plan-generation request is sent to the server, send only the occupation IDs/skill vectors needed for that request and do not persist them.

---

# 89. Prerequisite distance

For search/discovery only, compute a structural distance:

```text
0 = eligible now
1 = one prerequisite step
2 = two prerequisite steps
...
```

For OR rules, show the shortest verified branch.

This is not the same as number of semesters. Study-period availability determines actual earliest timing.

---

# 90. Unlock value

Optional soft preference:

> Prefer courses that unlock more later courses relevant to my plan/interests.

Calculate from the verified prerequisite graph.

Do not let unlock value override hard degree rules.

---

# 91. API design

Base:

```text
/api/v1
```

## Catalogue

```http
GET /catalogues
GET /catalogues/{year}/status
```

## Degrees

```http
GET /degrees?year=2027&audience=domestic
GET /degrees/{degree_id}?year=2027
GET /degrees/{degree_id}/requirements?year=2027
GET /degrees/{degree_id}/study-plan?year=2027
GET /degrees/{degree_id}/options?year=2027
```

## Courses

```http
GET /courses?year=2027&q=database
GET /courses/{course_id}?year=2027
GET /courses/{course_id}/degree-fit?year=2027&degree_id=...
```

## Search

```http
POST /search
```

## Planner

```http
POST /planner/validate
POST /planner/generate
POST /planner/path
```

## Compare

```http
POST /compare/degrees
```

## Assistant/router

```http
POST /assistant/query
```

## Careers

```http
GET /careers?q=robotics
GET /careers/{career_id}
POST /careers/match-degrees
```

---

# 92. Validation request example

```json
{
  "catalogue_year": 2027,
  "degree_id": "bcomp",
  "audience": "domestic",
  "options": ["aiml"],
  "items": [
    {
      "course": "COMP1002",
      "term": "2027-S1",
      "status": "COMPLETED"
    },
    {
      "course": "COMPxxxx",
      "term": "2027-S2",
      "status": "PLANNED"
    }
  ],
  "credits": []
}
```

Response:

```json
{
  "status": "INVALID",
  "course_checks": [
    {
      "course": "COMPxxxx",
      "term": "2027-S2",
      "status": "BLOCKED",
      "reasons": [
        {
          "type": "MISSING_PREREQUISITE",
          "missing": ["COMPyyyy"],
          "rule_id": "..."
        }
      ]
    }
  ],
  "degree_checks": [],
  "unknown_rules": [],
  "conditional_assumptions": []
}
```

---

# 93. Search request example

```json
{
  "query": "CAD elective",
  "catalogue_year": 2027,
  "degree_id": "bcomp",
  "plan_context": {
    "completed": ["COMP1002"]
  },
  "filters": {
    "prioritise_degree_compatible": true
  }
}
```

Response candidate:

```json
{
  "entity_type": "course",
  "course_code": "....",
  "match": {
    "type": "semantic",
    "evidence": [
      {
        "field": "learning_outcome",
        "text": "..."
      }
    ]
  },
  "degree_fit": "ELIGIBLE_ELECTIVE",
  "eligibility": "BLOCKED",
  "missing_prerequisites": ["..."]
}
```

---

# 94. Server privacy

Plan persistence is browser-only, but validation/generation requests may contain temporary plan state.

Rules:

- do not log plan request bodies;
- no third-party analytics containing plan payload;
- no persistent user ID required;
- no account cookie required;
- minimise data sent to hosted AI;
- do not send entire plans to AI when deterministic result structures are sufficient;
- document that server-side validation is transient.

A later fully local rule evaluator is possible, but not required for the first build.

---

# 95. IndexedDB schema

Suggested Dexie tables:

```text
profiles
plans
planItems
credits
preferences
savedCourses
savedSearches
cachedEntities
settings
```

Example TypeScript:

```ts
type LocalPlan = {
  id: string;
  schemaVersion: number;
  catalogueYear: number;
  degreeId: string;
  optionIds: string[];
  audience: "domestic" | "international";
  createdAt: string;
  updatedAt: string;
};
```

Use IndexedDB migrations as schemas evolve.

---

# 96. Import/export

Provide:

```text
Export plan
Export all local data
Import plan
Import all local data
Delete local data
```

Warn:

> Plans are stored in this browser. Clearing browser storage can remove them unless they have been exported.

Do not pretend cloud backup exists.

---

# 97. PWA/offline behaviour

Offline:

- open local plan;
- move course cards;
- view cached degree/course data;
- export plan.

May require connection:

- fresh catalogue;
- new semantic search;
- solver generation;
- AI explanation.

Show offline status clearly.

---

# 98. Caching

Public catalogue responses are highly cacheable.

Use:

```text
ETag
Cache-Control
catalogue revision
source hash
```

Planner requests are user-state-specific and should not be publicly cached.

---

# 99. Static catalogue exports

Publish versioned machine-readable snapshots:

```text
/catalogue/2027/degrees.json
/catalogue/2027/courses.json
/catalogue/2027/rules.json
```

Benefits:

- debugging;
- reproducibility;
- outside integrations;
- future offline client;
- easy fixtures.

No student data belongs in these files.

---

# 100. Public API possibility

The catalogue layer can later serve other Adelaide student projects.

Design for:

- versioned endpoints;
- documented schemas;
- explicit source metadata;
- rate limits;
- stable identifiers.

Do not promise long-term API stability until the rule model has settled.

---

# 101. Security

Use:

- strict Pydantic/request schemas;
- parameterised database operations;
- output encoding;
- CSP;
- dependency scanning;
- rate limits for expensive endpoints;
- request-size limits;
- crawler URL allowlist;
- no arbitrary URL-fetch endpoint;
- HTML sanitisation/stripping;
- environment-secret management.

The crawler should only fetch approved Adelaide University domains/paths.

---

# 102. Prompt-injection resistance

Treat scraped source text as untrusted data from the model's perspective.

AI call pattern:

```text
system rules
narrow structured task
allowed schema
<<< SOURCE DATA >>>
...
<<< END SOURCE DATA >>>
```

Scraped text must never select tools or alter the model's instructions.

Rule parsing needs no model tool access.

---

# 103. Search-query privacy

Default:

- process search;
- do not persist raw query tied to a user;
- saved searches stay local only;
- avoid analytics that store plan/interests by default.

If usage metrics are added, prefer aggregate operational metrics rather than raw personal queries.

---

# 104. Observability

For a small deployment:

- structured application logs;
- scrape-job logs;
- parser failure counts;
- API error rate;
- request latency;
- database health;
- catalogue revision status.

Do not log plan payloads.

---

# 105. Admin/developer review workflow

A developer review interface or CLI can show:

```text
Entity: COMPxxxx
Catalogue: 2027

Raw rule
"..."

Deterministic parser
FAILED: ...

AI candidate
[rule tree]

Checks
✓ references resolve
? connector ambiguous

[Approve override]
[Edit]
[Keep unknown]
```

For a personal/open-source build, a CLI + YAML override workflow may be preferable to building admin authentication.

---

# 106. CLI tooling

Suggested commands:

```bash
degreebook scrape degrees --year 2027
degreebook import courses --year 2027
degreebook parse rules --year 2027
degreebook validate catalogue --year 2027
degreebook embed --year 2027
degreebook career import onet
degreebook career import jsa
degreebook publish --year 2027
```

Support `--dry-run`.

---

# 107. Parser/search/model versioning

Persist:

```text
parser_version
rule_compiler_version
embedding_model_version
search_ranker_version
ai_prompt_version
```

If the embedding model changes, rebuild the relevant vector index rather than mixing vector spaces.

For AI rule parsing, retain:

```text
source_hash
prompt_version
model_id
candidate_output
validation_result
```

This is public-source processing, not user conversation storage.

---

# 108. Cheap deployment profile

For personal/small-group use:

```text
Frontend
- static/edge hosted Next.js where convenient

Backend
- one FastAPI instance

Database
- one PostgreSQL instance with pgvector

Jobs
- scheduled/CLI crawl and indexing

AI
- disabled or local by default
- hosted provider optional
```

Avoid separate search servers and queue infrastructure unless real usage requires them.

---

# 109. Local development

Docker Compose:

```text
postgres + pgvector
backend
web
```

Run ingestion tools manually during development.

Tests use fixtures rather than repeatedly scraping live pages.

---

# 110. Why PostgreSQL instead of reusing SQLite everywhere?

`courses-api` can keep SQLite.

Degreebook benefits from PostgreSQL for:

- multiple catalogue versions;
- complex relationships;
- JSONB AST storage;
- full-text/trigram search;
- pgvector;
- concurrent web access.

A fully local personal-only variant could use SQLite plus FTS/vector extensions later.

---

# 111. Data contract with `courses-api`

Use an adapter DTO:

```python
class UpstreamCourse(BaseModel):
    upstream_id: str
    institutional_course_id: str | None
    year: int
    code: str
    title: str
    units: int | None
    terms: list[str]
    overview: str | None
    learning_outcomes: list[str]
    assessments: list[AssessmentDTO]
    prerequisites_raw: str | None
    corequisites_raw: str | None
    antirequisites_raw: str | None
    university_wide_elective: bool | None
    source_url: str
```

Do not let Degreebook's internal schema depend directly on the upstream database tables.

---

# 112. Upstream contribution plan

Useful `courses-api` PRs/issues:

1. expose raw requisite strings;
2. add bulk export by year;
3. include scrape timestamp/hash;
4. review multi-year identity/uniqueness;
5. return structured term arrays;
6. add tests for logical requisite preservation;
7. allow export without class meeting data.

These changes improve the ecosystem but Degreebook should still work through its adapter if they are not merged.

---

# 113. Why degree scraping belongs outside `courses-api`

`courses-api` answers:

```text
What is this course?
```

Degreebook also needs to answer:

```text
What does this degree require?
How does a course satisfy the degree?
What sequence is valid?
What is the fastest path?
What elective matches this interest?
What careers/skills relate to the curriculum?
```

Keep those responsibilities in the Degreebook project.

---

# 114. Project implementation sequence

## Phase A — Data foundation

Build:

- versioned catalogue models;
- source snapshots;
- 2027 degree discovery;
- degree parser;
- course importer;
- source reconciliation;
- data-quality report;
- parser fixtures.

Exit criterion:

> Structured degree/course data can reproduce a degree's main requirements and source links.

## Phase B — Rule engine

Build:

- AST;
- deterministic parser;
- degree-rule compiler;
- prerequisite/corequisite/antirequisite compiler;
- evaluator;
- verification states;
- manual overrides;
- golden tests.

Exit criterion:

> Common real rules evaluate deterministically and unclear rules fail safely.

## Phase C — Planner

Build:

- IndexedDB state;
- course statuses;
- credits/waivers;
- drag/drop;
- requirement allocation;
- validation;
- prerequisite pathing.

Exit criterion:

> A current student can model their degree and see strict diagnostics.

## Phase D — Plan generator

Build:

- CP-SAT model;
- period availability;
- locked courses;
- assessment preferences;
- multiple alternatives;
- solver diagnostics.

Exit criterion:

> System generates valid plans or explains why selected constraints conflict.

## Phase E — Search

Build:

- lexical search;
- embeddings;
- hybrid retrieval;
- evidence;
- degree fit;
- eligibility;
- elective explorer.

Exit criterion:

> Concept queries such as CAD return evidence-backed courses with planner context.

## Phase F — Natural-language interface

Build:

- intent router;
- deterministic routing;
- optional local/hosted LLM;
- template explanations;
- structured model output.

Exit criterion:

> One search box handles the target question types without placing AI in charge of validity.

## Phase G — Career explorer

Build:

- JSA importer;
- O*NET importer;
- skill concepts;
- occupation-course matches;
- degree aggregation.

Exit criterion:

> Career exploration works from public data and course evidence without job listings.

## Phase H — Hardening

Build:

- staged publication;
- change detection;
- live smoke tests;
- PWA caching;
- accessibility pass;
- security review;
- deployment/docs.

---

# 115. MVP cut

A smaller first public build can include:

```text
2027 catalogue
course import
strict requisite parser
one-degree planner
local storage
drag/drop
degree validation
fastest prerequisite path
hybrid course search
source evidence
```

Defer initially if needed:

```text
career explorer
complex natural-language comparisons
AI-assisted rule parsing
large historical backfill
advanced solver objectives
```

This MVP still proves the hardest product idea.

---

# 116. First technical spike

Before building the visual UI, prove the rule loop.

Input:

```text
one 2027 degree
all referenced courses
raw requisite text
```

Output:

```text
parsed degree AST
parsed course requisite ASTs
course dependency graph
validation for synthetic student records
fastest path to a blocked course
list of unknown/unparsed rules
```

The key engineering question is:

> Can public source rules be converted into a strict machine representation safely enough for planning?

If the answer is yes, the remaining work is normal product engineering.

---

# 117. First end-to-end UI slice

A strong first demo:

```text
Open Bachelor of Computer Science
→ load official standard study plan
→ drag one course to another semester
→ validator updates
→ click blocked course
→ show missing prerequisite
→ show fastest path
→ search "CAD"
→ show evidence-backed electives
→ add one to plan
→ revalidate
```

This demonstrates the core product without needing every later feature.

---

# 118. Full feature checklist

## Catalogue

- [ ] multi-year degree crawler
- [ ] domestic/international data
- [ ] majors/minors/specialisations
- [ ] degree logistics/admission
- [ ] degree structure
- [ ] standard plans
- [ ] source snapshots
- [ ] change detection
- [ ] staged publication

## Courses

- [ ] `courses-api` importer
- [ ] raw requisites
- [ ] learning outcomes
- [ ] assessments
- [ ] offerings
- [ ] university-wide elective flag
- [ ] WIL flag
- [ ] source reconciliation

## Rules

- [ ] AST
- [ ] degree-rule parser
- [ ] requisite parser
- [ ] verified/provisional/unknown states
- [ ] AI candidate parsing
- [ ] manual overrides
- [ ] source evidence

## Planner

- [ ] IndexedDB state
- [ ] completed/current/planned
- [ ] credit types
- [ ] waivers
- [ ] drag/drop
- [ ] allocation
- [ ] continuous validation
- [ ] prerequisite path
- [ ] branches
- [ ] import/export

## Generator

- [ ] OR-Tools solver
- [ ] pacing options
- [ ] earliest-completion mode
- [ ] no-listed-exam preference
- [ ] balanced-assessment preference
- [ ] interest weighting
- [ ] target-course weighting
- [ ] locked courses
- [ ] diagnostics

## Search

- [ ] global search
- [ ] exact course lookup
- [ ] degree search
- [ ] semantic course search
- [ ] degree-fit ranking
- [ ] eligibility filters
- [ ] evidence display

## AI

- [ ] no-AI baseline
- [ ] provider abstraction
- [ ] local model option
- [ ] intent extraction
- [ ] rule candidate parsing
- [ ] explanation generation
- [ ] degree comparison prose

## Career

- [ ] JSA data
- [ ] O*NET data
- [ ] skill taxonomy
- [ ] occupation search
- [ ] course-skill matching
- [ ] degree aggregation
- [ ] source labels

## UI

- [ ] 2010s social-network shell
- [ ] degree profile
- [ ] course profile
- [ ] planner
- [ ] requirements
- [ ] electives
- [ ] compare
- [ ] careers
- [ ] data/source page
- [ ] mobile
- [ ] accessibility

---

# 119. Main technical risks

| Risk | Response |
|---|---|
| Adelaide HTML changes | Snapshots, semantic parsing, fixture tests, smoke tests, staged publication. |
| Rule prose is complex | Typed AST, deterministic grammar, AI candidate, manual override, `UNKNOWN`. |
| Current API loses AND/OR logic | Ingest raw requirement text. |
| Multi-year course identities collide | Separate identity from year-specific version. |
| AI hallucinates | AI never owns academic validity; schemas and evidence are required. |
| Semantic search is vague | Hybrid search plus exact evidence chunks. |
| No-exam claim is wrong | Use `NO_LISTED_EXAM`/`UNKNOWN`, retain source evidence. |
| Credit is misunderstood | Separate approved specific credit, generic credit, proposed credit and waiver. |
| Solver creates odd plans | Explicit hard constraints, configurable soft objectives, "Why here?" explanations. |
| Small project becomes expensive | One backend, one DB, local embeddings, optional LLM. |
| Browser storage is lost | Import/export and clear storage warnings. |
| Historical data disappears | Immutable snapshots and explicit missing-source states. |

---

# 120. Product naming direction

`Degreebook` fits the UI idea because it sounds like an old social-network-style academic hub without requiring social features.

Other possible names:

```text
Coursebook
StudyGrid
DegreeGrid
StudyMap
Adelaide Planner
CourseMap
```

The architecture should not depend on the final name.

---

# 121. Recommended final architecture

```text
Frontend
- Next.js + TypeScript
- dnd-kit
- Dexie / IndexedDB
- PWA

Backend
- FastAPI
- SQLAlchemy
- Alembic
- OR-Tools

Data
- PostgreSQL
- pgvector
- Postgres full-text search

Ingestion
- HTTP client
- BeautifulSoup/lxml
- Playwright fallback
- immutable source snapshots

AI
- local embeddings
- optional local small instruct model
- optional hosted adapter

Academic sources
- Adelaide University degree/course pages
- compsci-adl/courses-api

Career sources
- Jobs and Skills Australia
- O*NET

Deployment
- modular monolith
- one API
- one database
- one web app
- scheduled/CLI ingestion
```

---

# 122. Core implementation rule

The most important architecture rule is:

> **AI may help understand a query or propose an interpretation, but verified structured rules decide academic validity.**

That supports:

- strict validation;
- prerequisite pathing;
- generated plans;
- credit/waiver modelling;
- semantic electives;
- natural-language search;
- degree comparisons;
- career exploration;
- auditable explanations.

It also keeps the product useful with AI turned off.

---

# 123. Source references used for this specification

Accessed **27 September 2026**.

## Adelaide University

Degree catalogue stem supplied for the project:

```text
https://adelaide.edu.au/study/degrees/2027
```

Bachelor of Computer Science:

```text
https://adelaide.edu.au/study/degrees/bachelor-of-computer-science/dom/
```

Example current course page, Structured Data:

```text
https://adelaide.edu.au/study/courses/comp-1003/
```

Example year-qualified course page, Problem Solving and Programming:

```text
https://adelaide.edu.au/study/courses/2026/comp-1002/
```

## `courses-api`

```text
https://github.com/compsci-adl/courses-api
```

Repository files inspected for this design:

```text
README.md
src/server.py
src/models.py
src/schemas.py
src/data_parser.py
pyproject.toml
```

## Jobs and Skills Australia

```text
https://www.jobsandskills.gov.au/data
https://www.jobsandskills.gov.au/data/occupation-and-industry-profiles
```

## O*NET

```text
https://www.onetcenter.org/database.html
```

---

# 124. Final product definition

Degreebook should be treated as an **academic rules engine with a student-facing discovery and planning interface**, rather than an AI chatbot with a course database attached.

The layers are:

```text
official public academic data
        ↓
versioned structured catalogue
        ↓
verified degree/course rule AST
        ↓
validator + prerequisite graph + constraint solver
        ↓
hybrid search + skill/occupation graph
        ↓
natural-language router/explainer
        ↓
dense 2010s-inspired web interface
```

For a current student, the main value is:

```text
What do I still need, can I take this, and what is the fastest valid path?
```

For a future student:

```text
What degree fits what I want to learn, what will I actually study, and where can it lead?
```

For both:

```text
Show me the source and explain why.
```

That should be the standard applied to every major feature.
