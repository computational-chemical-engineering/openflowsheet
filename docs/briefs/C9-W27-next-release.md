# C9 — W27 rules for the next release's registration: several routes per method; the `Co`/`CO` clash (design lane, `specifier`)

Branch `wp/C9` from `main` `f880582`. Source: `docs/CLOUD_WORK.md` C9; Frank's answer L01-Q1 (`docs/FRANK_QUESTIONS.md:15`):
a small separate design-lane package, applied to **the next release's** W27 registration; **v0.2's W27 stays unchanged.**
Register numbering: **R-570…R-574**. ADR number if needed: **0045**.

## Constraint that shapes the deliverable
`docs/derivations/M06-W27-registration.md` is v0.2's registration. Its SHA-256 is pinned by preflight P2
(`benchmarks/m06/w27/preflight.py:57-65`) and recorded in the committed campaign record
(`benchmarks/m06/openidaes450/runs/w27-m07-83f825d/preflight.json:45`); it already has Amendments 1–4 (§20–§23), so
"Amendment 3" in CLOUD_WORK is a working label. **Do not edit that file, `registration.json`, `dry_illustration.json`,
`coverage.json` or any campaign record.** The rules go into a new registration document for the next release (or a
successor amendment file that the next release adopts), with its own generator check.

## Facts with anchors
- One route per method: W27-R20 (`docs/derivations/M06-W27-registration.md:276-290`; `routes_per_revision = 1`,
  `multiple_routes_per_revision`), W27-R24 (d)/(e) refusals (`:1107-1109`), W27-A14 (`:710`). Classifier:
  `benchmarks/m06/w27/coverage.py` (`check_snapshot` :153-212, `_route_reasons` :381-).
- The case clash: W27-R24 (c) spelling check casefolds `id`/`name`/`formula` (`benchmarks/m06/w27/coverage.py:168-181`),
  so a record `CO` (carbon monoxide) collides with the archive's `Co` (cobalt) and the snapshot is refused.
- The driver: S04's library route `pr-lib-v1` (method `cubic_pr`, same as `pr-c1-v1`), L01 spec findings F-1/F-2 and
  their recommended serving rule (`docs/derivations/L01-spec.md:378-386`): a group is served iff some route of its
  method serves it; units judged on the serving route with the fewest unit reasons, ties by provider id. S04's measured
  re-take (L01 spec §6, WO-L01-3) waits on this.
- The C2 split (`docs/derivations/C2-OpenIDAES-450-split-registration.md`, R-555) reads only `case_id`/`family`/`class`
  of coverage; any reclassification under the new rules must state its effect on the split's read fields (SPLIT-R12).

## Exit test
The new registration text (rules W27-Rxx for several routes per method, the serving rule, the case-sensitive formula
match or a registered `Co` element; refusals restated; numbered assertions), a generator or `--check` that encodes the
new tables without touching v0.2's committed files, register entries, and a build-lane work order for the classifier
change behind a registration-version switch (v0.2 behaviour byte-identical). Commit (`C9:` prefix, trailers). Report ≤ 150 words.

## Out of scope
Running coverage over held-out cases; S04's re-take itself (a later build step); any v0.2 record.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/C9-handoff.md`, stop.
