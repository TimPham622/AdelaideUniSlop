# Reviewed rule overrides

Put JSON overrides in a catalogue-year subdirectory. Each override requires `year`, `course`, `kind` (`prerequisite`, `corequisite`, or `antirequisite`), `rule` (a validated AST), `author`, `reviewed_at`, `source_hash`, `source_url`, and `reason`.

`source_hash` must exactly match the course source SHA-256 in the normalized catalogue. If a source changes, the replacement becomes UNKNOWN until reviewed again. Overrides and their provenance are retained on the course record. Missing provenance or invalid AST shapes reject publication.

A waiver assumption entered in the browser is never a published override. Do not use an override to manufacture unavailable offerings or automatically approve student credit.

Program rules are published in the normalized degree snapshot and guarded by expected structured-rule fixtures. Double-counting defaults to UNKNOWN. Any future program/year policy change needs authoritative provenance and corresponding evaluator/fixture review; no global default is inferred.
