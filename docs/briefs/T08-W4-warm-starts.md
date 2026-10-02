# Brief — T08 W4: compatible warm starts

**To:** `opus-engineer` (build lane). **From:** the session, 2026-09-29. **Branch:** `wp/T08`.
**Design (binding):** `docs/derivations/T08-build-first-spec.md` Part B — §B1 (source, compatibility,
incompatibility), §B2 (chain position, checks, records, identity), §B3 (contract surface — unchanged), §B5
(what judges V13 (e), including the source/target cases), §C.1 rows T08.B40–B50, §I W4. ADR 0024 (Proposed).
Frank's answers (2026-09-29): the request-named warm start is **v0.2**, not now (Q-B1); VERIFIED-only pool
(Q-B2); no locking, the selection is recorded (Q-B4).

## Scope (W4 only)

The runner lookup (`store-latest-verified-lineage-v1`), the `WarmStartCandidate` plumbing, the
`compatible_warm_start` source in the initializer chain on the revision path, the policy `T08-warm-v1`
(offered in `get_project.solve_policies`), the `warm_start` member of `solve-path.json`, the `r0_projection`
branch, and the rerun path (a rerun uses the recorded candidate, never the store). Read the T07 design
(`docs/design/T07-jobs-and-bindings.md`) only for the store/runner/bundle parts you touch.

## Gates

T08.B40–B50 and B26 (identity), plus `PATH=.venv/bin:$PATH ./scripts/check.sh` green. B50 is the agent
surface: the descriptions digest `6d13e13d…` and the request/response schemas unchanged — **no schema, MCP
tool, description file or ADR 0019 change**. If W4 cannot be done without one, stop and report.

## Establish first

- **Q-B3:** may the lookup read other principals' runs in the same project? Read T07 §10.1's rights (design note
  and `application/authz.py`). If project `read` covers all its jobs, yes; otherwise restrict to the caller's
  jobs and report it (the envelope then states it). Report which, with file:line.
- **The target case certifies cold.** §B5's target (the child revision with recycle fraction 0.95) must solve
  to `VERIFIED` from a cold start on the revision path. If it does not, **stop** — do not substitute another
  case.

## Forbidden — stop and report instead

- Anything touching the PTC-R1 case (W3 is blocked on a design question; do not create
  `benchmarks/t08/ptc_r1/`, and run nothing on the PTC-R1 flowsheet).
- Changing any existing policy's chain or any registered bundle's bytes (B49): every existing policy keeps
  an empty warm-start source and writes no `warm_start` member. Identity (B26): K05 minus-`t07` `9a7b4e6d…`,
  T02 floats `9a8a5baf…`, structural `915c97e8…`, `t07` `11bcb148…`, keys `t02`…`t06` byte-equal; whole
  document `3ed2911b…` — show it with the existing identity tests.
- Editing the spec, the ADRs, the YAML or `requirements.lock`. A warm start may change the starting point,
  never the problem: no path may write a specification, bound, tolerance or check policy from the candidate.
- If the design is wrong or under-determined, stop and report the question with file:line evidence.

## Working rules

Work in this checkout on `wp/T08`; nobody else edits it. Coherent commits starting `T08 W4:` and ending
with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` and
`Claude-Session: https://claude.ai/code/session_01D3snRb74o416XH4PPV2fAW`. Stage named paths only. Never set
`reviewed`. `.venv/bin/python`; the path has a space — quote it. Isolate any decision the spec left open in its
own commit and list it in the report. Budget: the user is near a weekly usage limit — read only what you need,
run targeted tests while developing and the full `check.sh` once at the end.

## Report

Commits, the Q-B3 answer, whether the target certified cold (numbers), each gate B40–B50/B26 with pass/fail
and measured values, `check.sh` (test count), your isolated decisions, and any question you stopped on.
