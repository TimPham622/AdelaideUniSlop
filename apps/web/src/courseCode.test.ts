import { readFileSync } from "node:fs";
import { expect, test } from "vitest";
import { isCourseCode } from "./courseCode";

const cases = JSON.parse(
  readFileSync(new URL("../../../data/course_code_cases.json", import.meta.url), "utf8"),
) as { valid: string[]; invalid: string[] };

test("shared Adelaide course-code contract", () => {
  for (const code of cases.valid) expect(isCourseCode(code)).toBe(true);
  for (const code of cases.invalid) expect(isCourseCode(code)).toBe(false);
});
