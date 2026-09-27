import type { Rule } from "../types";

export function RuleTree({ rule }: { rule: Rule }) {
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
          {rule.children?.map((child, index) => (
            <RuleTree key={index} rule={child} />
          ))}
        </>
      )}
    </div>
  );
}
