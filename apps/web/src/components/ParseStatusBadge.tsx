export function ParseStatusBadge({ status }: {
  status: "PARSED" | "UNPARSED" | "OVERRIDDEN_REVIEWED";
}) {
  const label = {
    PARSED: "Rules parsed",
    UNPARSED: "Rules need review",
    OVERRIDDEN_REVIEWED: "Reviewed rule override",
  }[status];
  return <span className={`badge ${status === "UNPARSED" ? "unknown" : "satisfied"}`}>{label}</span>;
}
