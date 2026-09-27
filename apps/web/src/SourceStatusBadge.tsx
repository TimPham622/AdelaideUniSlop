import type { SourceStatus } from "./types";

export function SourceStatusBadge({
  status,
}: {
  status: SourceStatus;
}) {
  const label = {
    SOURCE_VERIFIED: "Source verified",
    SOURCE_UNVERIFIED: "Source needs review",
    SOURCE_YEAR_MISMATCH: "Source year mismatch",
    SOURCE_MISSING: "Source missing",
  }[status];
  return (
    <span className={`badge ${status === "SOURCE_VERIFIED" ? "satisfied" : "unknown"}`}>
      {label}
    </span>
  );
}
