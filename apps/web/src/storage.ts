import Dexie, { type Table } from "dexie";
import { PlanSchema, migratePlan, newPlan, type Plan, type Catalogue } from "./types";
class LocalDatabase extends Dexie {
  plans!: Table<{ year: number; plan: Plan }, number>;
  planRecords!: Table<Plan, string>;
  catalogue!: Table<{ id: string; data: Catalogue }, string>;
  constructor() {
    super("adelaide-uni-slop");
    this.version(1).stores({ plans: "year", catalogue: "id" });
    this.version(2).stores({ plans: "year", planRecords: "id,catalogue_year", catalogue: "id" })
      .upgrade(async (transaction) => {
        const previous = await transaction.table("plans").toArray() as { year: number; plan: unknown }[];
        for (const row of previous)
          await transaction.table("planRecords").put(migratePlan(row.plan));
      });
  }
}
export const db = new LocalDatabase();
export async function loadPlan(year: number) {
  const row = await db.planRecords.where("catalogue_year").equals(year).first();
  return row ? PlanSchema.parse(row) : newPlan(year);
}
export async function listPlans() {
  return (await db.planRecords.toArray()).map((row) => PlanSchema.parse(row))
    .sort((a, b) => a.catalogue_year - b.catalogue_year || a.name.localeCompare(b.name));
}
export async function loadPlanById(id: string) {
  const row = await db.planRecords.get(id);
  return row ? PlanSchema.parse(row) : null;
}
export async function savePlan(plan: Plan) {
  await db.planRecords.put(PlanSchema.parse(plan));
}
export async function deletePlan(id: string) {
  await db.planRecords.delete(id);
}
export function parseImport(text: string) {
  if (new TextEncoder().encode(text).length > 262144)
    throw new Error("Plan files must be smaller than 256 KiB.");
  return migratePlan(JSON.parse(text));
}
export function exportPlan(plan: Plan) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(plan, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = `adelaide-uni-slop-${plan.catalogue_year === 2027 ? 2026 : plan.catalogue_year}.json`;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
