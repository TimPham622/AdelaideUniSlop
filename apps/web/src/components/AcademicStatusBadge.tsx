const statusText: Record<string, string> = {
  SATISFIED: "Satisfied",
  UNSATISFIED: "Not satisfied",
  UNKNOWN: "Unknown",
  CONDITIONAL: "Conditional",
  VALID: "Valid",
  INVALID: "Incomplete / invalid",
  INFEASIBLE: "No solution",
  TAKEABLE: "Takeable",
  BLOCKED: "Blocked",
};

export function AcademicStatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${status.toLowerCase()}`}>
      {statusText[status] ?? status.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}
