import { ArrowUpRight } from "lucide-react";
import type { Source } from "../types";

export function SourceLink({ source }: { source: Source }) {
  return (
    <a href={source.requested_url} target="_blank" rel="noreferrer">
      Official source <ArrowUpRight size={13} />
    </a>
  );
}
