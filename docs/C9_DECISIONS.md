# C9 — build decisions (W27 rules for the next release)

Append-only. One line per choice: `DECISION: <question> → <choice>. Alternative: <x>. Reversible by: <how>.`
- DECISION: where version 2's rules live → a new document `docs/derivations/W27-registration-v2.md` + `registration_v2.json` + its generator, v0.2's files untouched (R-570). Alternative: Amendment 5 inside `M06-W27-registration.md`. Reversible by: folding the text into the next release's registration copy.
- DECISION: numbering → own prefix W27v2-R/A and GC-V2. Alternative: continue W27-R69/A83 (C3 is renaming A80…A82 concurrently). Reversible by: a renumbering table in the document.
- DECISION: serving rule → serving routes only, min (unit-reason count, provider id); no-serve detail = every route's mismatch by provider id joined `;` (R-571). Alternative: first serving route in snapshot order; union of models. Reversible by: a version 3 rule; states A03–A07 show the difference.
- DECISION: refusal (d) → keep routes_per_revision = 1; replace "two routes of one method" by "duplicate provider id"; keep (e) (R-571). Alternative: drop (d) entirely. Reversible by: restoring the shared-method item (mutant `shared_method_refused`).
- DECISION: Co/CO → keep case folding; a case-only collision passes only by a reviewed `case_distinct` entry keyed to the CAS RN; `Co` distinct from 630-08-0, still `unidentified` (R-572). Alternative: case-sensitive formula/id match; alias `Co` → 7440-48-4. Reversible by: deleting the entry or adding an alias in a later version.
- DECISION: a route with no models (pr-lib-v1) → admitted; it judges every non-junction unit `no_model` (R-573). Alternative: refuse it. Reversible by: a refusal item (f).
- DECISION: version switch → explicit `registration_version`, default 1; version 2 has no default output path and refuses the committed `coverage.json` (R-570, R-574). Alternative: default 2 at the next release cut. Reversible by: the next release's registration flipping the default.
- DECISION: ADR → none (0045 unused): a benchmark-registration change, no blueprint/plan departure, no frozen interface. Alternative: ADR 0045. Reversible by: writing it if a reviewer finds a departure.
- DECISION: Frank questions → none; §9 Q-1 (re-report v0.2 under v2) proceeds on its default "no". Alternative: escalate Q-1. Reversible by: appending it to FRANK_QUESTIONS.md.
