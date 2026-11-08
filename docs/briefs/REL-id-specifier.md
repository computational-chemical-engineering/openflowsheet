# Specifier brief: the release evidence package id (`REL…`) — schema ADR, before 0.4.0's K3

Status: brief, 2026-11-08. Small design-lane item (RP review ruling 4, must-fix K-1, and N-4). **Do not spawn
sub-agents yourself.** Writes no production code: the build lane applies the pattern afterwards.

## The question

What exact additive widening of the evidence manifest's `work_package` pattern admits one release package id per
release, forever, without collisions — and how is a version mapped to it?

## Facts (all on main)

- Schema `schemas/evidence-manifest.schema.json` `properties.work_package.pattern` (ADR 0059 D1, **Accepted**):
  `^(?:[PKTMSR][0-9]{2}[a-z]?|F[0-9]|X[0-9]{2}[a-z]?|TX|MSG|ST|OPT|RRC|PrISMa)$`. ADR 0059
  (`docs/adr/0059-evidence-work-package-ids.md`) is the precedent to follow in form: D1–D3, rejected alternatives,
  acceptance evidence (isolated commit; `test_work_package_pattern_widening_is_additive` style exhaustive check;
  `tests/test_evidence_manifests.py` with every committed manifest unchanged). Its D3: named tracks get an id by
  amending D1 one alternative at a time; no generic upper-case pattern.
- Release procedure `docs/derivations/release-procedure.md` D1.5 (line ~93): the release of `X.Y.Z` has evidence
  package `REL` + the version's digits (0.4.0 → `REL040`); branch `wp/REL040`, manifest `evidence/REL040/<C>/manifest.json`,
  verdicts `docs/reviews/REL040-verdicts.md`, etc. Line ~393: the harvest tuple at 0.4.0 is `("evidence/REL040/",)`.
  Amendment A-7 (§17.1, line ~1102) defers the id to "the schema ADR of ruling 4".
- RP review `docs/reviews/RP-review.md` ruling 4 (line ~129): widen additively by `|REL[0-9]{3,}`, applied alone,
  tested like ADR 0059's check; RP's own manifest stays `S15` (C-22). **N-4** (line ~84): `REL` + digits collides once
  a component reaches 10 (1.10.0 and 11.0.0 both give `REL1100`); "settle it in the ADR of ruling 4".
- 0.3.0's release evidence was filed under `S13` (harvested); it does not move.
- Next free ADR number: 0074 (0071–0073 are OPT, RRC, WIT).

## Genuinely open

1. The N-4 mapping: e.g. fixed-width zero-padded components, a separator the pattern admits, or another
   unambiguous, order-preserving encoding — keeping `REL040` for 0.4.0 if possible (the procedure, its tests and
   defaults already use it; say exactly what changes if it cannot stay).
2. The exact regex alternative (closed, not generic) and what it must refuse.
3. Whether `release-procedure.md` D1.5 needs a numbered amendment (quote the replaced text) and the register line
   (drafted unnumbered).

## Deliverable

`docs/adr/0074-release-evidence-package-id.md` (Proposed; acceptance condition like ADR 0059's: applied alone by the
build lane with its tests), any D1.5 amendment text, numbered falsifiable acceptance assertions (accepted / refused
example lists, additivity check), the register line drafted unnumbered. Commit on **main** (docs-only, named paths,
message `docs: ADR 0074 release evidence package id`, with Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com> and
Claude-Session: https://claude.ai/code/session_014hjTc57iVNbNxYG2kezzvv). Report ≤ 20 lines, including whether Frank
must accept it or (as ADR 0059) it is accepted on its build-lane condition.

## Machine-load rule

TRS2 shared: `uptime` first; no test runs needed beyond a quick regex probe; another agent is building ST.

## Out of scope

The release procedure's other steps, ADR 0055, F-8, Q-11; ids for any package other than the release package.
