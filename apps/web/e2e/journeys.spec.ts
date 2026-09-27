import { test, expect } from "@playwright/test";

test("local plan survives edits, reload, export and versioned import", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load standard plan" }).click();
  await expect(page.getByLabel("Status for COMP1002")).toBeVisible();
  await page
    .getByLabel("Move COMP1002 to", { exact: true })
    .selectOption("2026-semester-2");
  await page
    .getByLabel("Status for COMP1002", { exact: true })
    .selectOption("COMPLETED");
  await expect(page.locator(".save-status")).toHaveText(
    "Saved in this browser",
  );
  await page.reload();
  await expect(
    page.getByLabel("Status for COMP1002", { exact: true }),
  ).toHaveValue("COMPLETED");
  await expect(
    page.getByLabel("Move COMP1002 to", { exact: true }),
  ).toHaveValue("2026-semester-2");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export plan", exact: true }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("adelaide-uni-slop-2026.json");
  const path = await file.path();
  await page.getByLabel("Import plan file").setInputFiles(path!);
  await page
    .getByRole("button", { name: "Import and replace", exact: true })
    .click();
  await expect(
    page.getByText("Plan imported and saved locally."),
  ).toBeVisible();
});

test("year and major browsing preserve separate plans and expose source uncertainty", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Load standard plan" }).click();
  await page.getByLabel("Catalogue year").selectOption("2027");
  await expect(page.locator(".course-card")).toHaveCount(0);
  await page
    .getByLabel("Study pathway")
    .selectOption({ label: "Human-Centred Computing" });
  await page.getByRole("button", { name: "Load standard plan" }).click();
  await expect(page.locator(".course-card").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Requirements", exact: true })
    .last()
    .click();
  await expect(page.getByText("Every requirement, explained")).toBeVisible();
  await page.getByLabel("Catalogue year").selectOption("2026");
  await page
    .getByRole("button", { name: "Study planner", exact: true })
    .click();
  await expect(page.getByLabel("Study pathway")).toHaveValue("general");
  await expect(page.getByLabel("Status for COMP1002")).toBeVisible();
});

test("corpus search shows X-series evidence and honest path results", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Search degrees, courses or ask a question")
    .fill("STATX100");
  await page
    .getByRole("button", { name: "Search", exact: true })
    .first()
    .click();
  await expect(page.locator(".search-card").first()).toBeVisible({
    timeout: 30000,
  });
  const course = page
    .locator(".search-card")
    .filter({ hasText: "Probability and Statistics" })
    .first();
  await expect(course.locator("blockquote").first()).toBeVisible();
  await course.getByRole("button", { name: "Add to plan" }).click();
  await course.locator(".search-card-title").click();
  await expect(page.getByRole("dialog")).toContainText("Requisites");
  await expect(page.getByRole("dialog")).toContainText("Source needs review");
  await page.getByRole("button", { name: "Fastest prerequisite path" }).click();
  const result = page.getByRole("dialog").last();
  await expect(result).toContainText("Planning result");
  await expect(result).not.toContainText(
    "Replace planned courses with this sequence",
  );
});

test("major changes fit and can-take uses a selected period", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Explore courses", exact: true }).click();
  await page.getByLabel("Course interest").fill("STATX100");
  await page.locator(".course-search button").click();
  await expect(page.locator(".search-card").filter({ hasText: "STATX100" })).toContainText(
    "Can count as university-wide elective",
  );
  await page.getByRole("button", { name: "Study planner", exact: true }).click();
  await page.getByLabel("Study pathway").selectOption({ label: "Artificial Intelligence and Machine Learning" });
  await page.getByRole("button", { name: "Explore courses", exact: true }).click();
  await page.getByLabel("Course interest").fill("STATX100");
  await page.locator(".course-search button").click();
  await expect(page.locator(".search-card").filter({ hasText: "STATX100" })).toContainText("Required");

  await page.getByLabel("Planning from period").selectOption("2026-semester-1");
  await page.getByLabel("Search degrees, courses or ask a question").fill(
    "Can I take COMP1002 next semester?",
  );
  await page.getByRole("button", { name: "Search", exact: true }).first().click();
  await expect(page.getByRole("dialog")).toContainText("Can I take COMP1002?");
  await expect(page.getByRole("dialog")).toContainText("Semester 2 · 2026");
  await expect(page.getByRole("dialog")).toContainText("Takeable");
  await page.getByLabel("Close dialog").click();
  await page.getByLabel("Catalogue year").selectOption("2027");
  await page.getByRole("button", { name: "Explore courses", exact: true }).click();
  await page.getByLabel("Course interest").fill("STATX100");
  await page.locator(".course-search button").click();
  await expect(page.locator(".search-card").filter({ hasText: "STATX100" })).toContainText(
    "Outside known degree requirements",
  );
});

test("generation refuses to invent future offerings and mobile layout fits", async ({
  page,
}) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Generate remaining plan" }).click();
  await expect(page.getByRole("dialog")).toContainText("Planning result");
  await expect(page.getByRole("dialog")).not.toContainText(
    "Replace planned courses with this sequence",
  );
  await page.getByLabel("Close dialog").click();
  const fits = await page.evaluate(
    () => document.documentElement.scrollWidth <= window.innerWidth,
  );
  expect(fits).toBe(true);
});

test("local provisional waivers remain distinct and survive reload", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("button", { name: "Credits & waivers", exact: true })
    .click();
  const creditForm = page.locator(".credit-form");
  await expect(creditForm).toBeVisible();
  await creditForm.locator("select").nth(0).selectOption("COMP1002");
  await creditForm.locator("select").nth(1).selectOption("WAIVER");
  await creditForm
    .locator("textarea")
    .fill("Provisional assumption, awaiting approval.");
  await page.getByRole("button", { name: "Add assumption" }).click();
  await expect(
    page.getByRole("heading", { name: "COMP1002 · Waiver" }),
  ).toBeVisible();
  await expect(page.locator(".save-status")).toHaveText(
    "Saved in this browser",
  );
  await page.reload();
  await page
    .getByRole("button", { name: "Credits & waivers", exact: true })
    .click();
  await expect(
    page.getByText("Provisional assumption, awaiting approval."),
  ).toBeVisible();
});
