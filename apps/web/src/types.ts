import { z } from "zod";
import { courseCodePattern } from "./courseCode";
export const AttemptSchema = z
  .object({
    id: z.string().min(1).max(100),
    course: z.string().regex(courseCodePattern),
    term: z
      .string()
      .regex(/^\d{4}-[a-z0-9-]+$/)
      .max(80),
    status: z.enum([
      "PLANNED",
      "CURRENT",
      "COMPLETED",
      "FAILED",
      "WITHDRAWN",
      "CREDIT",
    ]),
    locked: z.boolean(),
  })
  .strict();
const CreditSchema = z
  .object({
    id: z.string().min(1).max(100),
    kind: z.enum(["PROVISIONAL_CREDIT", "WAIVER"]),
    course: z.string().regex(courseCodePattern),
    note: z.string().max(1000),
  })
  .strict();
export const PlanSchema = z
  .object({
    schema_version: z.literal(1),
    name: z.string().min(1).max(100),
    year: z.number().int().min(2020).max(2100),
    degree: z.literal("bcomp"),
    option: z.string().max(150),
    attempts: z.array(AttemptSchema).max(200),
    credits: z.array(CreditSchema).max(100),
    max_units: z.number().int().min(6).max(48),
    preference: z.enum([
      "earliest",
      "avoid_exams_early",
      "prefer_no_exam",
      "balanced",
    ]),
  })
  .strict()
  .superRefine((p, ctx) => {
    for (const rows of [p.attempts, p.credits])
      if (new Set(rows.map((x) => x.id)).size !== rows.length)
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Duplicate record IDs",
        });
  });
export type Plan = z.infer<typeof PlanSchema>;
export type Attempt = z.infer<typeof AttemptSchema>;
export type Source = {
  requested_url: string;
  canonical_url: string;
  year: number;
  fetched_at: string;
  sha256: string;
  parser_version: string;
};
export type SourceStatus =
  | "SOURCE_VERIFIED"
  | "SOURCE_UNVERIFIED"
  | "SOURCE_YEAR_MISMATCH"
  | "SOURCE_MISSING";
export type Rule = {
  type: string;
  course?: string;
  children?: Rule[];
  raw?: string;
  warning?: string;
  units?: number;
  min_selected?: number;
  elective?: boolean;
};
export type Course = {
  code: string;
  year: number;
  title: string;
  units: number | null;
  level: number | null;
  level_source?: string;
  overview: string;
  outcomes: string[];
  assessments: string[];
  exam: string;
  elective: boolean | null;
  offerings: { key: string; label: string; year: number }[];
  raw: Record<string, string | null>;
  rules: Record<string, Rule>;
  source: Source;
  verification: string;
  source_status?: SourceStatus;
  parse_status?: "PARSED" | "UNPARSED" | "OVERRIDDEN_REVIEWED";
  year_status?: "MATCH" | "MISMATCH" | "UNKNOWN";
  warnings: string[];
};
export type Group = {
  id: string;
  title: string;
  units: number | null;
  codes: string[];
  raw: string;
  rule: Rule;
  verification: string;
};
export type Standard = { course: string; term: string; group: string };
export type Degree = {
  id: string;
  title: string;
  year: number;
  overview: string;
  total_units: number;
  summary_raw: string;
  summary_verified: boolean;
  groups: Group[];
  options: {
    id: string;
    title: string;
    groups: Group[];
    source: Source;
    standard_plan: Standard[];
    verification: string;
  }[];
  standard_plan: Standard[];
  source: Source;
  verification: string;
  source_status?: SourceStatus;
  parse_status?: "PARSED" | "UNPARSED" | "OVERRIDDEN_REVIEWED";
  year_status?: "MATCH" | "MISMATCH" | "UNKNOWN";
  course_references: Record<string, unknown>;
};
export type Catalogue = {
  degrees: Degree[];
  courses: Course[];
  revision: string;
};
export type Evaluation = {
  status: string;
  rule: Rule;
  children?: Evaluation[];
  actual_units?: number;
  message?: string;
};
export type Check = {
  id: string;
  course: string;
  term: string;
  status: string;
  reasons: {
    kind: string;
    status: string;
    message: string;
    evaluation?: Evaluation;
  }[];
};
export type Report = {
  status: string;
  course_checks: Check[];
  degree_checks: (Evaluation & {
    id: string;
    title: string;
    raw?: string;
    earned?: Evaluation;
  })[];
  earned_units: number;
  planned_units: number;
  unknown_count: number;
};
export type Solution = {
  status: string;
  message: string;
  attempts: Attempt[];
  optimal?: boolean;
  unknown_rules?: string[];
  blockers?: string[];
  horizon?: string[];
};
export type SearchResult = {
  course: Course;
  score: number;
  requirement_fit: "REQUIRED" | "COUNTS_AS_ELECTIVE" | "OUTSIDE_KNOWN_RULES" | "UNKNOWN";
  takeability: "TAKEABLE" | "BLOCKED" | "CONDITIONAL" | "UNKNOWN" | "NOT_EVALUATED";
  evidence: { field: string; text: string }[];
};
export type Takeability = {
  status: "TAKEABLE" | "BLOCKED" | "CONDITIONAL" | "UNKNOWN";
  target: string;
  period: string;
  reasons: { kind: string; status: string; message: string }[];
};
export const newPlan = (year: number): Plan => ({
  schema_version: 1,
  name: "My computer science plan",
  year,
  degree: "bcomp",
  option: "general",
  attempts: [],
  credits: [],
  max_units: 24,
  preference: "earliest",
});
