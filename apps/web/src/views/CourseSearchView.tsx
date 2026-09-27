import { ArrowUpRight, BookOpen, LoaderCircle, Plus, Search } from "lucide-react";
import { SourceLink } from "../components/SourceLink";
import { termLabel } from "../domain/period";
import type { Course, SearchResult } from "../types";

type Props = {
  query: string;
  onQueryChange: (query: string) => void;
  onSearch: (query?: string) => Promise<void>;
  searching: boolean;
  results: SearchResult[] | null;
  courses: Course[];
  mode: string;
  coverage: { indexed_courses: number; catalogue_courses: number } | null;
  compatible: boolean;
  onCompatibleChange: (compatible: boolean) => void;
  periods: string[];
  planningFromPeriod: string;
  onPlanningFromChange: (period: string) => void;
  fitMap: Record<string, SearchResult["requirement_fit"]>;
  onSelect: (course: Course) => void;
  onAdd: (course: Course) => void;
};

export function CourseSearchView({ query, onQueryChange, onSearch, searching, results,
  courses, mode, coverage, compatible, onCompatibleChange, periods,
  planningFromPeriod, onPlanningFromChange, fitMap, onSelect, onAdd }: Props) {
  const visibleResults = results ?? courses.map((course) => ({
    course,
    requirement_fit: fitMap[course.code] ?? "UNKNOWN" as const,
    takeability: "NOT_EVALUATED" as const,
    evidence: [],
    score: 0,
  }));
  return <>
    <div className="section-title">
      <div>
        <h2>Follow your curiosity</h2>
        <p>Search the currently ingested course corpus by what you want to learn. University-wide coverage is unverified.</p>
      </div>
      <BookOpen className="section-icon" />
    </div>
    <form className="course-search" onSubmit={(event) => {
      event.preventDefault();
      void onSearch();
    }}>
      <Search size={18} />
      <input aria-label="Course interest" value={query}
        onChange={(event) => onQueryChange(event.target.value)}
        placeholder="Try machine learning, programming, security…" />
      <button className="button primary" disabled={searching}>Search</button>
    </form>
    <div className="suggestions">
      Try{" "}
      {["machine learning", "programming", "security", "probability"].map((suggestion) => (
        <button key={suggestion} onClick={() => {
          onQueryChange(suggestion);
          void onSearch(suggestion);
        }}>{suggestion}</button>
      ))}
    </div>
    <div className="results-toolbar">
      <span>
        {results
          ? `${results.length} matches · ${mode === "HYBRID" ? "semantic + keyword search" : "keyword search"}`
          : `${courses.length} currently ingested courses`}
        {coverage ? ` · ${coverage.indexed_courses}/${coverage.catalogue_courses} vector indexed` : ""}
      </span>
      <label><input type="checkbox" checked={compatible}
        onChange={(event) => onCompatibleChange(event.target.checked)} />
        Known requirement fit first</label>
    </div>
    <label>
      Planning from period (for “can I take … next semester?”)
      <select aria-label="Planning from period" value={planningFromPeriod}
        onChange={(event) => onPlanningFromChange(event.target.value)}>
        <option value="">Choose a period</option>
        {periods.map((period) => <option key={period} value={period}>{termLabel(period)}</option>)}
      </select>
    </label>
    {searching ? (
      <div className="panel"><LoaderCircle className="spin" size={18} /> Finding evidence…</div>
    ) : visibleResults.map((result) => (
      <article className="search-card panel" key={result.course.code}>
        <div className="flex-between">
          <code>{result.course.code}</code>
          <span className="muted">{result.course.units ?? "?"} units</span>
        </div>
        <button className="search-card-title" onClick={() => onSelect(result.course)}>
          {result.course.title}<ArrowUpRight size={17} />
        </button>
        <div className="search-tags">
          <span>{result.requirement_fit === "COUNTS_AS_ELECTIVE"
            ? "Can count as university-wide elective"
            : result.requirement_fit === "REQUIRED"
              ? "Required"
              : result.requirement_fit === "OUTSIDE_KNOWN_RULES"
                ? "Outside known degree requirements"
                : "Fit unknown"}</span>
          <span>{result.course.exam === "NO_LISTED_EXAM"
            ? "No listed exam"
            : result.course.exam === "EXAM" ? "Exam listed" : "Assessment unknown"}</span>
        </div>
        {result.evidence.length ? result.evidence.slice(0, 2).map((evidence, index) => (
          <blockquote key={index}><small>{evidence.field.replaceAll("_", " ")}</small>{evidence.text}</blockquote>
        )) : <p className="course-excerpt">{result.course.overview ||
          "This course needs a verified catalogue source."}</p>}
        <div className="search-card-footer">
          <SourceLink source={result.course.source} />
          <button className="button secondary" onClick={() => onAdd(result.course)}>
            <Plus size={14} />Add to plan
          </button>
        </div>
      </article>
    ))}
    {results?.length === 0 && <div className="panel empty-state">
      No matching evidence in this catalogue. Try a broader interest.
    </div>}
  </>;
}
