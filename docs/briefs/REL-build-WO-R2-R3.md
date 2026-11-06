# Build brief: ADR 0055 WO-R2 and WO-R3 — the generic release gate and standing acceptances (0.4)

Status: brief, 2026-11-06. ADR 0055 (`docs/adr/0055-standing-release-procedure.md`; Frank: parts 1–3 now, D2 later).
Normative text: RP `docs/derivations/release-procedure.md` (WO-R1, 6714958d), line files `release/lines/{0.3,0.4}.json`,
schema `release/lines/release-line-v1.schema.json`, table `release/acceptances.md`. Branch `wp/RP` (create it from main
in a worktree `.claude/worktrees/rp`).

## Scope

- **WO-R2** `scripts/release_gate.py`: `v0_2_gate.py`'s engine imported, not copied; the line-file loader with RP's
  checks RP.L01–L10 (§3.4), `inherits`/`changed` (§3.2, REL.A01), gate resolution with RP's `role: inheritance/gate`
  (§3.5, finding F-1); the item-13 hook as RP states it **without D2's carry** (D2 deferred: no Φ, no
  `release_fingerprint.py`, no `release_carry.py`); the `release.yml` resolution (REL.A05). Acceptance: REL.A01–A05
  (ADR 0055 §10, lines 369–402), A03 byte-identical stdout against `scripts/v0_3_gate.py --rc a3e508e3` at the same
  checkout, A04's existing tests pass with node ids unchanged.
- **WO-R3** standing acceptances in `release_gate.py`: scope terms, extractors, lapse, dates and report lines exactly as
  RP §8 (8.1–8.5; §8.2's glob matching per finding F-2, refusing a glob that matches nothing). Acceptance: REL.A06–A10.
- Not in scope: WO-R4 (`ci.yml`), WO-R6 (`release_rc.py`, `release_evidence_manifest.py`), WO-R5 (D2).

## Rules

- RP is binding. Where RP leaves a choice or contradicts ADR 0055, follow RP and log it; where RP itself is silent on
  something that changes what the gate accepts, stop and report (design-lane question) — never loosen a check.
- `scripts/v0_2_gate.py`, `scripts/v0_3_gate.py` and their tests are released machinery: do not edit them. 0.3.0's legacy
  path must keep working (REL.A05).
- Build choices: decide, isolate, log in `docs/RP_DECISIONS.md`. Questions for the design lane are batched for the single
  reviewer pass over WO-R2…R6 (ADR 0055 §6).
- Run the tests you touch plus `tests/test_release_workflows.py`, `tests/test_m07_v0_2_gate.py`,
  `tests/test_m07a_v0_2_gate.py` and the V03 gate tests; ruff, ruff format, mypy on what you add. F0
  (`scripts/corpus_identity.py --check`) must PASS. The full gate runs before the merge, not now; you may push `wp/RP`.
- Commit on `wp/RP` only, named paths, messages `RP WO-R<n>: …`. Do not merge.
- Context cap about 150k tokens: commit what is complete, write `docs/RP_HANDOFF.md` (≤ 40 lines), stop.
- Never read, stat or touch `~/.config/procsim/`; do not read `/home/frankp/s10-papers/`, `~/.cache/seider3/`,
  `~/.cache/seider4/`; nothing under other worktrees. No subagents.

## Report (≤ 25 lines)

Commits; REL.A01–A10 pass/fail with the evidence (A03's byte comparison); F0 line; choices logged; design-lane
questions.
