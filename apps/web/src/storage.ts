import Dexie, { type Table } from "dexie";
import { PlanSchema, newPlan, type Plan, type Catalogue } from "./types";
class LocalDatabase extends Dexie {
  plans!: Table<{ year: number; plan: Plan }, number>;
  catalogue!: Table<{ id: string; data: Catalogue }, string>;
  constructor() {
    super("adelaide-uni-slop");
    this.version(1).stores({ plans: "year", catalogue: "id" });
  }
}
export const db = new LocalDatabase();
export async function loadPlan(year: number) {
  const row = await db.plans.get(year);
  return row ? PlanSchema.parse(row.plan) : newPlan(year);
}
export async function savePlan(plan: Plan) {
  await db.plans.put({ year: plan.year, plan: PlanSchema.parse(plan) });
}
export function parseImport(text: string) {
  if (new TextEncoder().encode(text).length > 262144)
    throw new Error("Plan files must be smaller than 256 KiB.");
  return PlanSchema.parse(JSON.parse(text));
}
export function exportPlan(plan: Plan) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(plan, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `adelaide-uni-slop-${plan.year}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
