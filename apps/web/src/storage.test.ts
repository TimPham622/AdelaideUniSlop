import { describe, it, expect } from "vitest";
import { parseImport } from "./storage";
import { newPlan } from "./types";
describe("Versioned plan recovery", () => {
  it("round trips a complete plan", () => {
    const p = newPlan(2026);
    expect(parseImport(JSON.stringify(p))).toEqual(p);
  });
  it("rejects unknown versions and malformed attempts", () => {
    expect(() =>
      parseImport(JSON.stringify({ ...newPlan(2026), schema_version: 3 })),
    ).toThrow();
    expect(() =>
      parseImport(
        JSON.stringify({
          ...newPlan(2026),
          attempts: [{ course: "COMP1001" }],
        }),
      ),
    ).toThrow();
  });
  it("rejects oversized imports and unknown data", () => {
    expect(() => parseImport(" ".repeat(262145))).toThrow();
    expect(() =>
      parseImport(JSON.stringify({ ...newPlan(2026), studentPassword: "no" })),
    ).toThrow();
  });
  it("migrates a version-one plan without losing attempts or pathway", () => {
    const old = {
      schema_version: 1, name: "Old plan", year: 2027, degree: "bcomp",
      option: "aiml", attempts: [{ id: "a", course: "COMP1001",
        term: "2027-semester-1", status: "COMPLETED", locked: true }],
      credits: [], max_units: 18, preference: "balanced",
    };
    const migrated = parseImport(JSON.stringify(old));
    expect(migrated).toMatchObject({ schema_version: 2, catalogue_year: 2027,
      degree_id: "bcomp", option_ids: ["aiml"], attempts: old.attempts });
  });
});
