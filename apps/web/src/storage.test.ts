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
      parseImport(JSON.stringify({ ...newPlan(2026), schema_version: 2 })),
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
});
