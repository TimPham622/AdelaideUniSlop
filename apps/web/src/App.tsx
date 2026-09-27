import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  BookOpen,
  Search,
  LayoutGrid,
  ListChecks,
  GraduationCap,
  ArrowUpRight,
  Download,
  Upload,
  Plus,
  X,
  Check,
  ChevronRight,
  CircleHelp,
  ShieldCheck,
  GitBranch,
  Sparkles,
  LockKeyhole,
  GripVertical,
  ExternalLink,
  Database,
  AlertTriangle,
  LoaderCircle,
  Trash2,
  SlidersHorizontal,
  CalendarDays,
} from "lucide-react";
import { api } from "./api";
import { db, loadPlan, savePlan, exportPlan, parseImport } from "./storage";
import {
  newPlan,
  type Plan,
  type Catalogue,
  type Course,
  type Report,
  type Rule,
  type Solution,
  type SearchResult,
  type Source,
  type Attempt,
} from "./types";

type Tab =
  "planner" | "requirements" | "courses" | "degree" | "credits" | "sources";
const statusText: Record<string, string> = {
  SATISFIED: "Satisfied",
  UNSATISFIED: "Not satisfied",
  UNKNOWN: "Unknown",
  CONDITIONAL: "Conditional",
  VALID: "Valid",
  INVALID: "Incomplete / invalid",
  INFEASIBLE: "No solution",
};
function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status.toLowerCase()}`}>
      {statusText[status] ?? status.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}
function termLabel(term: string) {
  const [year, ...rest] = term.split("-");
  return `${rest.join(" ").replace(/^\w/, (s) => s.toUpperCase())} · ${year}`;
}
function RuleTree({ rule }: { rule: Rule }) {
  return (
    <div className="rule-tree">
      {rule.type === "COURSE" ? (
        <code>{rule.course}</code>
      ) : rule.type === "UNKNOWN" ? (
        <span>{rule.warning ?? "Needs source review"}</span>
      ) : rule.type === "ALL" && !rule.children?.length ? (
        <span>No listed requirement</span>
      ) : (
        <>
          <strong>
            {rule.type === "ALL"
              ? "All of"
              : rule.type === "ANY"
                ? `At least ${rule.min_selected ?? 1} of`
                : rule.type === "NOT"
                  ? "Must not have"
                  : `${rule.type.replaceAll("_", " ")}: ${rule.units ?? ""}`}
          </strong>
          {rule.children?.map((r, i) => (
            <RuleTree key={i} rule={r} />
          ))}
        </>
      )}
    </div>
  );
}
function SourceLink({ source }: { source: Source }) {
  return (
    <a href={source.requested_url} target="_blank" rel="noreferrer">
      Official source <ArrowUpRight size={13} />
    </a>
  );
}
function Dialog({
  title,
  close,
  children,
}: {
  title: string;
  close: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = ref.current;
    const before = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      before?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        close();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="dialog-head">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={close}
        >
          <X size={20} />
        </button>
      </div>
      <div className="dialog-body">{children}</div>
    </dialog>
  );
}
export default function App() {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null);
  const [plan, setPlan] = useState<Plan>(newPlan(2026));
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState<Tab>("planner");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [saved, setSaved] = useState(false);
  const [cached, setCached] = useState(false);
  const [report, setReport] = useState<Report | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [mode, setMode] = useState("");
  const [compatible, setCompatible] = useState(true);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<Course | null>(null);
  const [solution, setSolution] = useState<Solution | null>(null);
  const [busy, setBusy] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [importCandidate, setImportCandidate] = useState<Plan | null>(null);
  const [creditCourse, setCreditCourse] = useState("");
  const [creditKind, setCreditKind] = useState<"PROVISIONAL_CREDIT" | "WAIVER">(
    "PROVISIONAL_CREDIT",
  );
  const [creditNote, setCreditNote] = useState("");
  const [extraTerms, setExtraTerms] = useState<string[]>([]);
  const [addTerm, setAddTerm] = useState(false);
  const [termYear, setTermYear] = useState(2029);
  const [termName, setTermName] = useState("semester-1");
  const upload = useRef<HTMLInputElement>(null);
  const searchSequence = useRef(0);
  const planRef = useRef(plan);
  planRef.current = plan;
  const change = (next: Plan) => {
    setPlan(next);
    setReport(null);
    setSaved(false);
  };
  useEffect(() => {
    let active = true;
    async function init() {
      try {
        const data = await api<Catalogue>("/catalogue");
        if (active) setCatalogue(data);
        await db.catalogue.put({ id: "latest", data });
      } catch {
        const old = await db.catalogue.get("latest").catch(() => undefined);
        if (active) {
          if (old) {
            setCatalogue(old.data);
            setCached(true);
          } else
            setError(
              "Cannot load the catalogue. Start the API, then reload this page.",
            );
        }
      }
      try {
        const stored = await loadPlan(2026);
        if (active) {
          setPlan(stored);
          setLoaded(true);
        }
      } catch {
        if (active)
          setError(
            "Browser storage could not be opened. Your existing local data has not been overwritten.",
          );
      }
    }
    void init();
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    if (!loaded) return;
    let active = true;
    setSaved(false);
    void savePlan(plan)
      .then(() => {
        if (active) setSaved(true);
      })
      .catch(() => {
        if (active)
          setError(
            "Plan could not be saved in this browser. Export a copy before leaving.",
          );
      });
    return () => {
      active = false;
    };
  }, [plan, loaded]);
  useEffect(() => {
    if (!loaded || !catalogue) return;
    const abort = new AbortController();
    setReport(null);
    const timer = setTimeout(() => {
      void api<Report>("/plan/validate", plan, abort.signal)
        .then(setReport)
        .catch((e) => {
          if (e.name !== "AbortError")
            setError(`Validation unavailable: ${e.message}`);
        });
    }, 300);
    return () => {
      clearTimeout(timer);
      abort.abort();
    };
  }, [plan, catalogue, loaded]);
  const degree = catalogue?.degrees.find((d) => d.year === plan.year);
  const courses = useMemo(
    () => catalogue?.courses.filter((c) => c.year === plan.year) ?? [],
    [catalogue, plan.year],
  );
  const courseMap = useMemo(
    () => new Map(courses.map((c) => [c.code, c])),
    [courses],
  );
  const periods = useMemo(
    () =>
      Array.from(
        new Set([
          ...Array.from(
            { length: 6 },
            (_, i) =>
              `${plan.year + Math.floor(i / 2)}-semester-${(i % 2) + 1}`,
          ),
          ...plan.attempts.map((a) => a.term),
          ...courses.flatMap((c) => c.offerings.map((o) => o.key)),
          ...extraTerms,
        ]),
      ).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
    [plan.year, plan.attempts, courses, extraTerms],
  );
  const groupList =
    plan.option === "general"
      ? degree?.groups
      : degree?.options.find((o) => o.id === plan.option)?.groups;
  const required = new Set(groupList?.flatMap((g) => g.codes) ?? []);
  const checks = new Map(report?.course_checks.map((c) => [c.id, c]));
  async function switchYear(year: number) {
    try {
      await savePlan(plan);
      const next = await loadPlan(year);
      change(next);
      setSelected(null);
      setResults(null);
      setExtraTerms([]);
      setNotice(`Opened your separate ${year} catalogue plan.`);
    } catch {
      setError("Could not switch catalogue safely. Export your plan first.");
    }
  }
  function addCourse(course: Course, term = periods[0]) {
    if (
      plan.attempts.some(
        (a) =>
          a.course === course.code &&
          !["FAILED", "WITHDRAWN"].includes(a.status),
      )
    ) {
      setNotice(`${course.code} is already in your plan.`);
      return;
    }
    change({
      ...plan,
      attempts: [
        ...plan.attempts,
        {
          id: crypto.randomUUID(),
          course: course.code,
          term,
          status: "PLANNED",
          locked: false,
        },
      ],
    });
    setNotice(`${course.code} added to ${termLabel(term)}.`);
  }
  function updateAttempt(id: string, patch: Partial<Attempt>) {
    change({
      ...plan,
      attempts: plan.attempts.map((a) =>
        a.id === id ? { ...a, ...patch } : a,
      ),
    });
  }
  function standardPlan() {
    const rows =
      (plan.option === "general"
        ? degree?.standard_plan
        : degree?.options.find((o) => o.id === plan.option)?.standard_plan) ??
      [];
    const retained = plan.attempts.filter(
      (a) => a.status !== "PLANNED" || a.locked,
    );
    const existing = new Set(retained.map((a) => a.course));
    const attempts = rows
      .filter((r) => courseMap.has(r.course) && !existing.has(r.course))
      .map((r) => ({
        id: crypto.randomUUID(),
        course: r.course,
        term: r.term,
        status: "PLANNED" as const,
        locked: false,
      }));
    change({ ...plan, attempts: [...retained, ...attempts] });
    setNotice(
      "Official suggested sequence loaded. Elective choices and unverified offerings still need review.",
    );
  }
  async function generate(target?: string) {
    setBusy(true);
    setError("");
    const snapshot = plan;
    try {
      const data = await api<Solution>(
        target ? "/plan/path" : "/plan/generate",
        target ? { plan: snapshot, target } : snapshot,
      );
      if (planRef.current === snapshot) setSolution(data);
      else
        setNotice(
          "Plan changed during calculation. Run it again for the updated plan.",
        );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function doSearch(value = query) {
    if (!value.trim()) return;
    const sequence = ++searchSequence.current;
    setSearching(true);
    setError("");
    try {
      const route = await api<{ intent: string; course: string | null }>(
        "/route",
        { query: value, year: plan.year },
      );
      if (sequence !== searchSequence.current) return;
      if (route.intent === "PLAN_GENERATE") {
        await generate();
        return;
      }
      if (route.intent === "PLAN_VALIDATE") {
        setTab("requirements");
        return;
      }
      if (route.intent === "PREREQUISITE_PATH" && route.course) {
        await generate(route.course);
        return;
      }
      if (route.intent === "DEGREE_SEARCH") {
        setTab("degree");
        setNotice(
          "The first catalogue release covers Bachelor of Computer Science.",
        );
        return;
      }
      setTab("courses");
      const response = await api<{ results: SearchResult[]; mode: string }>(
        "/search",
        { query: value, year: plan.year, compatible_first: compatible },
      );
      if (sequence === searchSequence.current) {
        setResults(response.results);
        setMode(response.mode);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      if (sequence === searchSequence.current) setSearching(false);
    }
  }
  const navItems: { id: Tab; label: string; icon: ReactNode }[] = [
    { id: "degree", label: "Degree overview", icon: <GraduationCap /> },
    { id: "planner", label: "My study planner", icon: <LayoutGrid /> },
    { id: "requirements", label: "Requirements", icon: <ListChecks /> },
    { id: "credits", label: "Credits & waivers", icon: <ShieldCheck /> },
    { id: "courses", label: "Explore courses", icon: <BookOpen /> },
    { id: "sources", label: "Catalogue & sources", icon: <Database /> },
  ];
  if (!catalogue || !degree)
    return (
      <div className="loading-screen">
        <GraduationCap size={44} />
        <h1>adelaide uni slop</h1>
        {error ? (
          <>
            <p role="alert">{error}</p>
            <button onClick={() => location.reload()}>Try again</button>
          </>
        ) : (
          <p>
            <LoaderCircle className="spin" size={16} /> Opening the catalogue…
          </p>
        )}
      </div>
    );
  const earned = report?.earned_units ?? 0;
  const target = degree.total_units ?? 144;
  return (
    <>
      <header className="topbar">
        <a
          className="wordmark"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("planner");
          }}
        >
          <span className="logo">
            <GraduationCap size={23} />
          </span>
          adelaide uni slop<span className="beta">BETA</span>
        </a>
        <form
          className="global-search"
          onSubmit={(e) => {
            e.preventDefault();
            void doSearch();
          }}
        >
          <Search size={17} />
          <input
            aria-label="Search degrees, courses or ask a question"
            placeholder="Find a course, an interest, a way through your degree…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button aria-label="Search" disabled={searching}>
            {searching ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <ChevronRight size={18} />
            )}
          </button>
        </form>
        <button className="local-indicator" onClick={() => setPrivacy(true)}>
          <LockKeyhole size={14} />
          <span>Just your browser</span>
        </button>
      </header>
      <div className="app-shell">
        <aside className="sidebar">
          <div className="workspace-tag">YOUR LITTLE ACADEMIC CORNER</div>
          <div className="degree-avatar">
            <span>CS</span>
            <div>
              <strong>Computer Science</strong>
              <small>Undergraduate · BCOMP</small>
            </div>
          </div>
          <div className="sidebar-label">MY DEGREE</div>
          <nav>
            {navItems.slice(0, 4).map((n) => (
              <button
                key={n.id}
                className={tab === n.id ? "active" : ""}
                onClick={() => setTab(n.id)}
              >
                {n.icon}
                {n.label}
                {n.id === "planner" && (
                  <span className="nav-count">{plan.attempts.length}</span>
                )}
              </button>
            ))}
            <div className="sidebar-label explore-label">DISCOVER</div>
            {navItems.slice(4).map((n) => (
              <button
                key={n.id}
                className={tab === n.id ? "active" : ""}
                onClick={() => setTab(n.id)}
              >
                {n.icon}
                {n.label}
              </button>
            ))}
          </nav>
          <div className="sidebar-note">
            <div className="small-symbol">✳</div>
            <strong>
              A degree is a big thing.
              <br />
              Take it one semester at a time.
            </strong>
            <p>Plan it. Change it. Make it yours.</p>
          </div>
          <button className="privacy-link" onClick={() => setPrivacy(true)}>
            <CircleHelp size={14} /> Privacy & local storage
          </button>
          <div className="sidebar-footer">
            Independent student tool.
            <br />
            Not affiliated with Adelaide University.
          </div>
        </aside>
        <main>
          <div className="breadcrumb">
            My degree <ChevronRight size={12} /> Bachelor of Computer Science
          </div>
          <section className="degree-cover">
            <div className="cover-grid" />
            <div className="cover-top">
              <span className="cover-label">YOUR DEGREE, UNTANGLED.</span>
              <span className="cover-code">BCOMP / ADELAIDE</span>
            </div>
            <div className="cover-bottom">
              <div>
                <h1>
                  Bachelor of
                  <br />
                  Computer Science<span className="coral-dot">.</span>
                </h1>
                <p>One plan. Every possibility.</p>
              </div>
              <div className="cover-seal">
                <GraduationCap size={38} />
                <span>
                  MAKE A PLAN
                  <br />
                  MAKE IT YOURS
                </span>
              </div>
            </div>
          </section>
          <div className="degree-toolbar">
            <div className="degree-meta">
              <span>
                <BookOpen size={14} />
                {target} units
              </span>
              <span>
                <CalendarDays size={14} />3 year suggested sequence
              </span>
              <span className="source-state">
                <span />
                Source-backed catalogue
              </span>
            </div>
            <label className="year-select">
              Catalogue{" "}
              <select
                aria-label="Catalogue year"
                value={plan.year}
                onChange={(e) => void switchYear(Number(e.target.value))}
              >
                {catalogue.degrees.map((d) => (
                  <option key={d.year} value={d.year}>
                    {d.year}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="page-tabs">
            {(["planner", "requirements", "courses", "degree"] as Tab[]).map(
              (t) => (
                <button
                  key={t}
                  className={tab === t ? "selected" : ""}
                  onClick={() => setTab(t)}
                >
                  {
                    {
                      planner: "Study planner",
                      requirements: "Requirements",
                      courses: "Find electives",
                      degree: "Overview",
                      credits: "Credits",
                      sources: "Sources",
                    }[t]
                  }
                </button>
              ),
            )}
            <span className="save-status">
              {saved ? (
                <Check size={13} />
              ) : (
                <LoaderCircle size={13} className="spin" />
              )}
              {saved ? "Saved in this browser" : "Saving locally…"}
            </span>
          </div>
          {error && (
            <div className="notice error" role="alert">
              <AlertTriangle size={17} />
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {cached && (
            <div className="notice warning">
              Showing a locally cached catalogue. Server validation needs a
              connection.
            </div>
          )}
          <div className="content-layout">
            <div className="primary-content">
              {tab === "planner" && (
                <>
                  <div className="section-title">
                    <div>
                      <h2>Your study planner</h2>
                      <p>A little structure for the big picture.</p>
                    </div>
                    <div className="toolbar-buttons">
                      <button
                        className="icon-button"
                        title="Export plan"
                        aria-label="Export plan"
                        onClick={() => exportPlan(plan)}
                      >
                        <Download size={17} />
                      </button>
                      <button
                        className="icon-button"
                        title="Import plan"
                        aria-label="Import plan"
                        onClick={() => upload.current?.click()}
                      >
                        <Upload size={17} />
                      </button>
                    </div>
                  </div>
                  <div className="planner-controls">
                    <label>
                      Study pathway
                      <select
                        aria-label="Study pathway"
                        value={plan.option}
                        onChange={(e) =>
                          change({ ...plan, option: e.target.value })
                        }
                      >
                        <option value="general">
                          General computer science
                        </option>
                        {degree.options.map((o) => (
                          <option key={o.id} value={o.id}>
                            {o.title}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button className="button secondary" onClick={standardPlan}>
                      Load standard plan
                    </button>
                  </div>
                  <div className="plan-tools">
                    <span>
                      <GripVertical size={15} />
                      Drag cards or use “Move to” below each course.
                    </span>
                    <button onClick={() => setTab("courses")}>
                      <Plus size={14} />
                      Add a course
                    </button>
                  </div>
                  <div className="period-grid">
                    {periods.map((term) => {
                      const items = plan.attempts.filter(
                        (a) => a.term === term,
                      );
                      const units = items.reduce(
                        (n, a) => n + (courseMap.get(a.course)?.units ?? 0),
                        0,
                      );
                      const known = catalogue.courses.some((c) =>
                        c.offerings.some((o) => o.key === term),
                      );
                      return (
                        <section
                          className="period"
                          key={term}
                          data-testid={`period-${term}`}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            const id = e.dataTransfer.getData("text/plain");
                            const a = plan.attempts.find((a) => a.id === id);
                            if (a && !a.locked) updateAttempt(id, { term });
                          }}
                        >
                          <div className="period-heading">
                            <h3>{termLabel(term)}</h3>
                            <span
                              className={
                                units > plan.max_units ? "overload" : ""
                              }
                            >
                              {units}/{plan.max_units} units
                            </span>
                          </div>
                          {!known && (
                            <div className="period-unknown">
                              Offerings not yet verified
                            </div>
                          )}
                          <div className="period-courses">
                            {items.map((a) => {
                              const c = courseMap.get(a.course);
                              const check = checks.get(a.id);
                              return (
                                <article
                                  className={`course-card ${a.status === "COMPLETED" ? "completed" : ""}`}
                                  key={a.id}
                                  draggable={!a.locked}
                                  onDragStart={(e) =>
                                    e.dataTransfer.setData("text/plain", a.id)
                                  }
                                >
                                  <div className="card-code">
                                    <button onClick={() => c && setSelected(c)}>
                                      {a.course}
                                    </button>
                                    <span>{c?.units ?? "?"} units</span>
                                    <button
                                      className="icon-button"
                                      aria-label={`${a.locked ? "Unlock" : "Lock"} ${a.course}`}
                                      onClick={() =>
                                        updateAttempt(a.id, {
                                          locked: !a.locked,
                                        })
                                      }
                                    >
                                      {a.locked ? (
                                        <LockKeyhole size={12} />
                                      ) : (
                                        <GripVertical size={13} />
                                      )}
                                    </button>
                                  </div>
                                  <button
                                    className="card-title"
                                    onClick={() => c && setSelected(c)}
                                  >
                                    {c?.title ?? "Course absent from catalogue"}
                                  </button>
                                  <div className="card-tags">
                                    <span>
                                      {required.has(a.course)
                                        ? "Required course"
                                        : "Elective choice"}
                                    </span>
                                    {check && <Badge status={check.status} />}
                                  </div>
                                  {check && check.status !== "SATISFIED" && (
                                    <button
                                      className="diagnostic-link"
                                      onClick={() => c && setSelected(c)}
                                    >
                                      {check.reasons[0]?.message}{" "}
                                      <ChevronRight size={12} />
                                    </button>
                                  )}
                                  <div className="card-edit">
                                    <select
                                      aria-label={`Status for ${a.course}`}
                                      value={a.status}
                                      onChange={(e) =>
                                        updateAttempt(a.id, {
                                          status: e.target
                                            .value as Attempt["status"],
                                        })
                                      }
                                    >
                                      {(
                                        [
                                          "PLANNED",
                                          "CURRENT",
                                          "COMPLETED",
                                          "FAILED",
                                          "WITHDRAWN",
                                          "CREDIT",
                                        ] as const
                                      ).map((s) => (
                                        <option key={s} value={s}>
                                          {s === "CREDIT"
                                            ? "Approved credit"
                                            : s
                                                .toLowerCase()
                                                .replace(/^\w/, (x) =>
                                                  x.toUpperCase(),
                                                )}
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      className="icon-button"
                                      aria-label={`Remove ${a.course}`}
                                      disabled={a.locked}
                                      onClick={() =>
                                        change({
                                          ...plan,
                                          attempts: plan.attempts.filter(
                                            (x) => x.id !== a.id,
                                          ),
                                        })
                                      }
                                    >
                                      <X size={13} />
                                    </button>
                                  </div>
                                  <label className="move-label">
                                    Move to
                                    <select
                                      aria-label={`Move ${a.course} to`}
                                      disabled={a.locked}
                                      value={a.term}
                                      onChange={(e) =>
                                        updateAttempt(a.id, {
                                          term: e.target.value,
                                        })
                                      }
                                    >
                                      {periods.map((p) => (
                                        <option key={p} value={p}>
                                          {termLabel(p)}
                                        </option>
                                      ))}
                                    </select>
                                  </label>
                                </article>
                              );
                            })}
                            {items.length === 0 && (
                              <button
                                className="empty-period"
                                onClick={() => setTab("courses")}
                              >
                                <Plus size={19} />
                                <span>A little room to explore</span>
                                <small>Find a course to add</small>
                              </button>
                            )}
                          </div>
                        </section>
                      );
                    })}
                  </div>
                  <button
                    className="add-period"
                    onClick={() => setAddTerm(true)}
                  >
                    <Plus size={15} />
                    Add a study period
                  </button>
                  <div className="planner-footnote">
                    <ShieldCheck size={16} />
                    <span>
                      Suggested study periods are editable. Only published
                      offerings can be verified.
                    </span>
                  </div>
                </>
              )}
              {tab === "requirements" && (
                <>
                  <div className="section-title">
                    <div>
                      <h2>Every requirement, explained</h2>
                      <p>
                        Projected progress and earned progress stay separate.
                      </p>
                    </div>
                  </div>
                  {!report ? (
                    <div className="panel">Checking rules…</div>
                  ) : (
                    report.degree_checks.map((check) => (
                      <section className="requirement panel" key={check.id}>
                        <div className="flex-between">
                          <h3>{check.title}</h3>
                          <Badge status={check.status} />
                        </div>
                        <p>{check.raw ?? check.rule.raw}</p>
                        {check.actual_units !== undefined &&
                          check.actual_units !== null && (
                            <p className="unit-summary">
                              {check.actual_units} projected units ·{" "}
                              {check.earned?.actual_units ?? 0} earned
                            </p>
                          )}
                        {check.message && (
                          <p className="warning-text">{check.message}</p>
                        )}
                        <details>
                          <summary>Inspect structured rule</summary>
                          <RuleTree rule={check.rule} />
                        </details>
                        <SourceLink source={degree.source} />
                      </section>
                    ))
                  )}
                </>
              )}
              {tab === "courses" && (
                <>
                  <div className="section-title">
                    <div>
                      <h2>Follow your curiosity</h2>
                      <p>Find courses by what you want to learn.</p>
                    </div>
                    <BookOpen className="section-icon" />
                  </div>
                  <form
                    className="course-search"
                    onSubmit={(e) => {
                      e.preventDefault();
                      void doSearch();
                    }}
                  >
                    <Search size={18} />
                    <input
                      aria-label="Course interest"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      placeholder="Try CAD, robotics, 3D modelling…"
                    />
                    <button className="button primary" disabled={searching}>
                      Search
                    </button>
                  </form>
                  <div className="suggestions">
                    Try{" "}
                    {["CAD", "3D modelling", "machine learning", "design"].map(
                      (q) => (
                        <button
                          key={q}
                          onClick={() => {
                            setQuery(q);
                            void doSearch(q);
                          }}
                        >
                          {q}
                        </button>
                      ),
                    )}
                  </div>
                  <div className="results-toolbar">
                    <span>
                      {results
                        ? `${results.length} matches · ${mode === "HYBRID" ? "semantic + keyword search" : "keyword search"}`
                        : `${courses.length} catalogue courses`}
                    </span>
                    <label>
                      <input
                        type="checkbox"
                        checked={compatible}
                        onChange={(e) => {
                          setCompatible(e.target.checked);
                          setResults(null);
                        }}
                      />
                      Degree-compatible first
                    </label>
                  </div>
                  {searching ? (
                    <div className="panel">
                      <LoaderCircle className="spin" size={18} /> Finding
                      evidence…
                    </div>
                  ) : (
                    (
                      results ??
                      courses.map((c) => ({
                        course: c,
                        degree_fit: required.has(c.code)
                          ? "REQUIRED"
                          : c.elective
                            ? "ELECTIVE_CANDIDATE"
                            : "UNKNOWN",
                        evidence: [],
                        score: 0,
                      }))
                    ).map((result) => (
                      <article
                        className="search-card panel"
                        key={result.course.code}
                      >
                        <div className="flex-between">
                          <code>{result.course.code}</code>
                          <span className="muted">
                            {result.course.units ?? "?"} units
                          </span>
                        </div>
                        <button
                          className="search-card-title"
                          onClick={() => setSelected(result.course)}
                        >
                          {result.course.title}
                          <ArrowUpRight size={17} />
                        </button>
                        <div className="search-tags">
                          <span>
                            {result.degree_fit === "ELECTIVE_CANDIDATE"
                              ? "Potential university-wide elective"
                              : result.degree_fit === "REQUIRED"
                                ? "In this degree"
                                : result.degree_fit === "OUTSIDE_DEGREE"
                                  ? "Outside degree elective rules"
                                  : "Degree fit needs review"}
                          </span>
                          <span>
                            {result.course.exam === "NO_LISTED_EXAM"
                              ? "No listed exam"
                              : result.course.exam === "EXAM"
                                ? "Exam listed"
                                : "Assessment unknown"}
                          </span>
                        </div>
                        {result.evidence.length ? (
                          result.evidence.slice(0, 2).map((e, i) => (
                            <blockquote key={i}>
                              <small>{e.field.replaceAll("_", " ")}</small>
                              {e.text}
                            </blockquote>
                          ))
                        ) : (
                          <p className="course-excerpt">
                            {result.course.overview ||
                              "This course needs a verified catalogue source."}
                          </p>
                        )}
                        <div className="search-card-footer">
                          <SourceLink source={result.course.source} />
                          <button
                            className="button secondary"
                            onClick={() => addCourse(result.course)}
                          >
                            <Plus size={14} />
                            Add to plan
                          </button>
                        </div>
                      </article>
                    ))
                  )}
                  {results?.length === 0 && (
                    <div className="panel empty-state">
                      No matching evidence in this catalogue. Try a broader
                      interest.
                    </div>
                  )}
                </>
              )}
              {tab === "degree" && (
                <>
                  <div className="section-title">
                    <div>
                      <h2>Meet your degree</h2>
                      <p>Computer science, with a path of your own.</p>
                    </div>
                    <Badge
                      status={
                        degree.verification === "VERIFIED"
                          ? "SATISFIED"
                          : "UNKNOWN"
                      }
                    />
                  </div>
                  <section className="panel">
                    <h3>Degree structure</h3>
                    <p>{degree.summary_raw}</p>
                    <div className="structure-bars">
                      {degree.groups.map((g) => (
                        <div key={g.id}>
                          <span>{g.title}</span>
                          <strong>{g.units ?? "?"} units</strong>
                        </div>
                      ))}
                    </div>
                    <SourceLink source={degree.source} />
                  </section>
                  <h3 className="subheading">Choose your direction</h3>
                  <button
                    className="major-card panel"
                    onClick={() => {
                      change({ ...plan, option: "general" });
                      setTab("planner");
                    }}
                  >
                    <div>
                      <h3>General computer science</h3>
                      <p>Follow the discipline course pathway.</p>
                    </div>
                    <ChevronRight size={20} />
                  </button>
                  {degree.options.map((o) => (
                    <div className="panel major-card" key={o.id}>
                      <div>
                        <h3>{o.title}</h3>
                        <p>
                          {o.groups.find((g) => g.id === "major-courses")
                            ?.raw ?? "Explore this major’s requirements."}
                        </p>
                        <SourceLink source={o.source} />
                      </div>
                      <button
                        className="icon-button"
                        aria-label={`Select ${o.title}`}
                        onClick={() => {
                          change({ ...plan, option: o.id });
                          setTab("planner");
                        }}
                      >
                        <ChevronRight size={20} />
                      </button>
                    </div>
                  ))}
                </>
              )}
              {tab === "credits" && (
                <>
                  <div className="section-title">
                    <div>
                      <h2>Credits & waivers</h2>
                      <p>
                        Keep assumptions explicit. Keep official progress
                        distinct.
                      </p>
                    </div>
                  </div>
                  <div className="panel">
                    <h3>Add a local assumption</h3>
                    <p>
                      Provisional credit can conditionally satisfy a named
                      course. A waiver affects only that course’s prerequisites
                      and grants no units.
                    </p>
                    <form
                      className="credit-form"
                      onSubmit={(e) => {
                        e.preventDefault();
                        if (!creditCourse) return;
                        change({
                          ...plan,
                          credits: [
                            ...plan.credits,
                            {
                              id: crypto.randomUUID(),
                              course: creditCourse,
                              kind: creditKind,
                              note: creditNote,
                            },
                          ],
                        });
                        setCreditNote("");
                      }}
                    >
                      <label>
                        Course
                        <select
                          required
                          value={creditCourse}
                          onChange={(e) => setCreditCourse(e.target.value)}
                        >
                          <option value="">Choose a course</option>
                          {courses.map((c) => (
                            <option value={c.code} key={c.code}>
                              {c.code} · {c.title}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Assumption type
                        <select
                          value={creditKind}
                          onChange={(e) =>
                            setCreditKind(e.target.value as typeof creditKind)
                          }
                        >
                          <option value="PROVISIONAL_CREDIT">
                            Provisional course credit
                          </option>
                          <option value="WAIVER">
                            Prerequisite waiver for this course
                          </option>
                        </select>
                      </label>
                      <label>
                        Notes
                        <textarea
                          value={creditNote}
                          maxLength={1000}
                          onChange={(e) => setCreditNote(e.target.value)}
                        />
                      </label>
                      <button className="button primary">
                        <Plus size={14} />
                        Add assumption
                      </button>
                    </form>
                  </div>
                  {plan.credits.map((c) => (
                    <div className="panel" key={c.id}>
                      <div className="flex-between">
                        <h3>
                          {c.course} ·{" "}
                          {c.kind === "WAIVER"
                            ? "Waiver"
                            : "Provisional credit"}
                        </h3>
                        <button
                          className="icon-button"
                          aria-label={`Remove assumption ${c.course}`}
                          onClick={() =>
                            change({
                              ...plan,
                              credits: plan.credits.filter(
                                (x) => x.id !== c.id,
                              ),
                            })
                          }
                        >
                          <Trash2 size={15} />
                        </button>
                      </div>
                      <Badge status="CONDITIONAL" />
                      <p>{c.note || "No supporting notes recorded."}</p>
                    </div>
                  ))}
                </>
              )}
              {tab === "sources" && (
                <>
                  <div className="section-title">
                    <div>
                      <h2>Nothing up our sleeves</h2>
                      <p>
                        Official sources. Explicit uncertainty. Inspectable
                        rules.
                      </p>
                    </div>
                  </div>
                  <div className="panel">
                    <h3>Catalogue {plan.year}</h3>
                    <p>
                      Retrieved{" "}
                      {new Date(degree.source.fetched_at).toLocaleString(
                        "en-AU",
                      )}
                    </p>
                    <SourceLink source={degree.source} />
                    <dl>
                      <dt>Parser</dt>
                      <dd>{degree.source.parser_version}</dd>
                      <dt>Degree source SHA-256</dt>
                      <dd className="hash">{degree.source.sha256}</dd>
                      <dt>Catalogue revision</dt>
                      <dd className="hash">{catalogue.revision}</dd>
                      <dt>Published course offerings</dt>
                      <dd>
                        {courses.filter((c) => c.offerings.length).length} of{" "}
                        {courses.length} course records
                      </dd>
                    </dl>
                    <div className="notice warning">
                      A year-qualified URL can return a different year. Those
                      course records remain unverified; offerings are never
                      extrapolated.
                    </div>
                  </div>
                  <div className="panel">
                    <h3>What the labels mean</h3>
                    {["SATISFIED", "UNSATISFIED", "UNKNOWN", "CONDITIONAL"].map(
                      (s, i) => (
                        <p key={s}>
                          <Badge status={s} />{" "}
                          {
                            [
                              "The structured check passed.",
                              "A known requirement has not been met.",
                              "The available source cannot establish the answer.",
                              "This depends on a local assumption.",
                            ][i]
                          }
                        </p>
                      ),
                    )}
                    <p>
                      Double-counting is unknown unless the program’s policy is
                      explicitly verified. The same course contributes total
                      degree units only once.
                    </p>
                  </div>
                </>
              )}
            </div>
            <aside className="right-column">
              <section className="progress-panel panel">
                <div className="eyebrow">THE BIG PICTURE</div>
                <h3>Your degree progress</h3>
                <div className="progress-number">
                  {earned}
                  <span> / {target} units</span>
                </div>
                <div className="progress-track">
                  <span
                    style={{
                      width: `${Math.min(100, (earned / target) * 100)}%`,
                    }}
                  />
                </div>
                <p className="progress-caption">Completed & approved credit</p>
                <div className="progress-row">
                  <span>In your plan</span>
                  <strong>{report?.planned_units ?? "—"} units</strong>
                </div>
                <div className="progress-row">
                  <span>Still to earn</span>
                  <strong>{Math.max(0, target - earned)} units</strong>
                </div>
                <div className="status-box">
                  <div className="flex-between">
                    <strong>Plan check</strong>
                    {report ? (
                      <Badge status={report.status} />
                    ) : (
                      <span className="muted">Checking…</span>
                    )}
                  </div>
                  <p>
                    {report?.status === "VALID"
                      ? "All applicable checks pass."
                      : report?.unknown_count
                        ? `${report.unknown_count} checks need source verification.`
                        : "Add your courses to see what’s satisfied and what’s still missing."}
                  </p>
                  <button onClick={() => setTab("requirements")}>
                    See every requirement <ChevronRight size={13} />
                  </button>
                </div>
              </section>
              <section className="generate-panel panel">
                <div className="generator-icon">
                  <GitBranch size={21} />
                </div>
                <h3>A way forward</h3>
                <p>
                  Build a remaining plan using verified rules and published
                  offerings.
                </p>
                <label>
                  Study load
                  <select
                    aria-label="Maximum units per period"
                    value={plan.max_units}
                    onChange={(e) =>
                      change({ ...plan, max_units: Number(e.target.value) })
                    }
                  >
                    {[6, 12, 18, 24, 30].map((u) => (
                      <option key={u} value={u}>
                        {u} units per period
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Prefer
                  <select
                    aria-label="Planning preference"
                    value={plan.preference}
                    onChange={(e) =>
                      change({
                        ...plan,
                        preference: e.target.value as Plan["preference"],
                      })
                    }
                  >
                    <option value="earliest">Earliest completion</option>
                    <option value="avoid_exams_early">Avoid exams early</option>
                    <option value="prefer_no_exam">Fewer listed exams</option>
                    <option value="balanced">Balanced exam load</option>
                  </select>
                </label>
                <button
                  className="button primary full-width"
                  disabled={busy}
                  onClick={() => void generate()}
                >
                  {busy ? (
                    <LoaderCircle className="spin" size={15} />
                  ) : (
                    <Sparkles size={15} />
                  )}
                  Generate remaining plan
                </button>
                <small>Deterministic planning. No generative AI.</small>
              </section>
              <section className="tip-card">
                <span className="tip-label">A GOOD PLACE TO START</span>
                <h3>What are you curious about?</h3>
                <p>
                  A course title doesn’t tell the whole story. Search the skills
                  you’d like to learn.
                </p>
                <button
                  onClick={() => {
                    setQuery("CAD");
                    void doSearch("CAD");
                  }}
                >
                  Explore CAD courses <ArrowUpRight size={14} />
                </button>
              </section>
              <div className="right-footnote">
                <ShieldCheck size={15} />
                <p>
                  Your plan stays in this browser.
                  <br />
                  <button onClick={() => exportPlan(plan)}>
                    Export a copy
                  </button>{" "}
                  to keep it safe.
                </p>
              </div>
            </aside>
          </div>
          <footer className="main-footer">
            <span>adelaide uni slop</span>
            <span>Built for figuring it out.</span>
            <button onClick={() => setPrivacy(true)}>Privacy & data</button>
          </footer>
        </main>
      </div>
      <input
        ref={upload}
        className="visually-hidden"
        type="file"
        accept=".json,application/json"
        aria-label="Import plan file"
        onChange={async (e) => {
          const file = e.target.files?.[0];
          if (!file) return;
          try {
            if (file.size > 262144)
              throw new Error("File is larger than 256 KiB.");
            const imported = parseImport(await file.text());
            if (!catalogue.degrees.some((d) => d.year === imported.year))
              throw new Error("The imported catalogue year is not available.");
            setImportCandidate(imported);
          } catch (e) {
            setError(`Import rejected: ${(e as Error).message}`);
          }
          e.target.value = "";
        }}
      />
      {selected && (
        <Dialog title={selected.code} close={() => setSelected(null)}>
          <h2 className="course-modal-title">{selected.title}</h2>
          <div className="search-tags">
            <span>{selected.units ?? "?"} units</span>
            <span>{selected.exam.replaceAll("_", " ").toLowerCase()}</span>
            <Badge
              status={
                selected.verification === "VERIFIED" ? "SATISFIED" : "UNKNOWN"
              }
            />
          </div>
          <p>{selected.overview}</p>
          {selected.warnings.map((w, i) => (
            <div className="notice warning" key={i}>
              {w}
            </div>
          ))}
          <h3>Learning outcomes</h3>
          <ul className="outcomes">
            {selected.outcomes.map((o, i) => (
              <li key={i}>{o}</li>
            ))}
          </ul>
          <h3>Requisites</h3>
          {Object.entries(selected.rules).map(([kind, rule]) => (
            <section className="requisite" key={kind}>
              <strong>{kind.replace(/^\w/, (s) => s.toUpperCase())}</strong>
              <p>{selected.raw[kind] ?? "Source field is missing"}</p>
              <RuleTree rule={rule} />
            </section>
          ))}
          <h3>Your plan diagnostics</h3>
          {report?.course_checks
            .filter((c) => c.course === selected.code)
            .map((c) => (
              <div className="panel" key={c.id}>
                <Badge status={c.status} />
                <p>{termLabel(c.term)}</p>
                {c.reasons.map((r, i) => (
                  <p key={i}>{r.message}</p>
                ))}
              </div>
            ))}
          <h3>Known offerings</h3>
          <p>
            {selected.offerings.length
              ? selected.offerings.map((o) => termLabel(o.key)).join(" · ")
              : "No verified offerings for this catalogue year."}
          </p>
          <h3>Listed assessment</h3>
          <ul>
            {selected.assessments.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
          <SourceLink source={selected.source} />
          <div className="dialog-actions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => void generate(selected.code)}
            >
              <GitBranch size={15} />
              Fastest prerequisite path
            </button>
            <button
              className="button primary"
              onClick={() => addCourse(selected)}
            >
              <Plus size={15} />
              Add to plan
            </button>
          </div>
        </Dialog>
      )}
      {solution && (
        <Dialog title="Planning result" close={() => setSolution(null)}>
          <Badge status={solution.status} />
          <h3>{solution.message}</h3>
          {solution.optimal === false && (
            <p className="warning-text">
              A valid sequence was found, but optimality was not proved within
              the time limit.
            </p>
          )}
          {solution.attempts.length > 0 && (
            <ol className="solution-list">
              {solution.attempts.map((a) => (
                <li key={a.id}>
                  <strong>{a.course}</strong> {courseMap.get(a.course)?.title}
                  <span>{termLabel(a.term)}</span>
                </li>
              ))}
            </ol>
          )}
          {solution.unknown_rules?.length ? (
            <details>
              <summary>
                Unresolved source rules ({solution.unknown_rules.length})
              </summary>
              <ul>
                {solution.unknown_rules.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </details>
          ) : null}
          {solution.horizon && (
            <p className="muted">
              Verified horizon:{" "}
              {solution.horizon.map(termLabel).join(", ") || "none"}.
            </p>
          )}
          {solution.status === "VALID" && solution.attempts.length > 0 && (
            <button
              className="button primary"
              onClick={() => {
                change({ ...plan, attempts: solution.attempts });
                setSolution(null);
                setSelected(null);
                setTab("planner");
              }}
            >
              Replace planned courses with this sequence
            </button>
          )}
        </Dialog>
      )}
      {privacy && (
        <Dialog
          title="Your browser. Your plan."
          close={() => setPrivacy(false)}
        >
          <p>
            Your plans are saved in this browser’s IndexedDB. There is no
            account, cloud backup, or student database.
          </p>
          <p>
            Validation and generation send your plan to the API for transient
            calculation. Search queries are processed transiently. The
            application does not log plan bodies or queries and has no
            analytics.
          </p>
          <p>
            In-memory rate limiting uses your connection IP for up to one
            minute. Local embeddings support search; generative AI is disabled.
          </p>
          <div className="notice warning">
            Clearing browser storage removes local plans. Export a copy before
            clearing it.
          </div>
          <button className="button primary" onClick={() => exportPlan(plan)}>
            <Download size={15} />
            Export current plan
          </button>
        </Dialog>
      )}
      {importCandidate && (
        <Dialog
          title="Review imported plan"
          close={() => setImportCandidate(null)}
        >
          <p>
            <strong>{importCandidate.name}</strong> · {importCandidate.year}
          </p>
          <p>
            {importCandidate.attempts.length} course attempts and{" "}
            {importCandidate.credits.length} assumptions. Importing replaces the
            saved plan for this catalogue year.
          </p>
          <div className="dialog-actions">
            <button
              className="button secondary"
              onClick={() => exportPlan(plan)}
            >
              Export current plan first
            </button>
            <button
              className="button primary"
              onClick={() => {
                change(importCandidate);
                setImportCandidate(null);
                setResults(null);
                setNotice("Plan imported and saved locally.");
              }}
            >
              Import and replace
            </button>
          </div>
        </Dialog>
      )}
      {addTerm && (
        <Dialog title="Add a study period" close={() => setAddTerm(false)}>
          <form
            className="credit-form"
            onSubmit={(e) => {
              e.preventDefault();
              setExtraTerms([...extraTerms, `${termYear}-${termName}`]);
              setAddTerm(false);
            }}
          >
            <label>
              Calendar year
              <input
                type="number"
                min={2020}
                max={2100}
                value={termYear}
                onChange={(e) => setTermYear(Number(e.target.value))}
              />
            </label>
            <label>
              Period key
              <input
                pattern="[a-z0-9]+(-[a-z0-9]+)*"
                value={termName}
                required
                onChange={(e) => setTermName(e.target.value)}
              />
            </label>
            <p>Adding a period does not establish course availability.</p>
            <button className="button primary">Add period</button>
          </form>
        </Dialog>
      )}
    </>
  );
}
