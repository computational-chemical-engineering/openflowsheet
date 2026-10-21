# ADR 0008 Amendment 2 — transient-readiness re-check at the 0.2.0 cut (design lane, `architect`)

**Requested by Frank, 2026-10-18.** Run at the 0.2.0 cut commit K (after M07 merges into main). No spend, no dynamic code.

## The question
Do the v0.2 additions keep a later transient capability *additive* (ADR 0008 "Additive or refactor"), or did any of
them reintroduce a lock-in point? Per finding: where, the cost of fixing it now vs at the transient package, and a
recommended action (none / test / text / code change with its own ADR).

## Why
R-001 and ADR 0008 Amendment 1 (2026-09-26, ~37 000 lines) were checked before v0.2. Since then v0.2 added external
model execution and records (ADR 0033), external models in a flowsheet solve (ADR 0034), model replacement and
promotion (ADR 0035), surrogate units (ADR 0036/0037), the C1 reactor boundary and PR route (ADR 0026/0027), M03
sensitivities and the NLP adapter (ADR 0031/0032), the trust-region adapter (ADR 0038–0040), the web shell (ADR 0030),
job kinds such as `surrogate_study`.

## Check against
ADR 0008 D1–D4 (P-1 no time at the evaluation boundary; P-2 `state_sha256` = exactly `x`; P-3 per-row `accumulation`
declarations, no central mass-matrix recipe), Amendment 1 (U1/U2 energy holdup is `U`; J1–J3, J5 job outputs; X1–X10,
U–H constraints on the transient ADR) and Frank's answers (Q1, Q-A1…Q-A5). `tests/test_adr_0008_transient_readiness.py`
(44 passed on main `4edcb5a`, 2026-10-18) — does it reach the new model kinds (external, surrogate, stand-in)?
Known point to judge: an external reactor is a steady input→output map with no exposed holdup; say what its dynamic
variant would require and whether anything should be recorded now.

## Deliverable
ADR 0008 "Amendment 2" (dated section), a register update to R-001, and work orders for any test or text change
(build lane, one branch). ≤ 200-word report.

## Session brief (cloud, 2026-10-21; package C1, branch `wp/C1`, from `main` `3c10e97`)

Added by the build lane for the cloud run. The 0.2.0 cut has happened (tag `v0.2.0`, M07 merged `8a06b91`); `main`
`3c10e97` is K's successor with docs-only changes, so judge at `main`.

**Facts with anchors**
- ADR 0008: `docs/adr/0008-transient-extension-readiness.md` — D1 :24, D2 :33, D3 :42, D4 :81, "Additive or refactor"
  :559, Amendment 1 :580 (rulings :588, :603; U–H :634; open questions :660; work orders :672; gates :696; R-001 draft
  :703). Register R-001: `docs/decision-register.md:21`.
- The readiness test `tests/test_adr_0008_transient_readiness.py` (534 lines): A1–A3 :68-:95 (context fields,
  protocol signatures, pairing fields), H1–H6 :122-:172 (state hash), M1–M5 :237-:285 (accumulation registry, which
  reads the registered SYN-001 equations), U1/U1b :420/:450, U2/U2b :497/:517.
- Accumulation declarations appear in `src/openflowsheet/models/syn001/*.py` and `src/openflowsheet/models/c1/feed.py`
  (:73, :82, :91); grep for `accumulation` in the other `models/c1/*.py` (reactor.py 555 lines, boundary.py 607 lines,
  reactor_standin.py, flash.py, heater.py, mixer.py, splitter.py, sink.py) to see which C1 rows declare it.
- v0.2 surfaces to check: external execution `src/openflowsheet/adapters/external/{protocol.py,launcher.py}`,
  experiments `adapters/experiments/{request,runner,store,backends}.py`, reactor `adapters/pymrm/`, C1 boundary
  `models/c1/boundary.py`, surrogate `studies/surrogate/*.py` (reactor.py mentions accumulation), trust region
  `studies/trust_region/` (projection.py mentions accumulation), replacement `application/replacement.py`, jobs
  `application/jobs/`, web shell `apps/`. ADRs 0026, 0027, 0030–0042 under `docs/adr/`.
- Register numbering for this package: **R-495…R-499**.

**Exit test**
1. ADR 0008 gains a dated "Amendment 2" section: per finding — where (file:line), lock-in or not, cost now vs at the
   transient package, recommended action (none / test / text / code change with its own ADR).
2. R-001 register update text, and register entries in R-495… appended to `docs/decision-register.md`.
3. Work orders for any test or text change (build lane). If a work order is a pure test extension (e.g. reaching M/A
   checks into C1, external or surrogate kinds), you may write and run it yourself on `wp/C1`.
4. `.venv/bin/python -m pytest -q tests/test_adr_0008_transient_readiness.py` still passes (run it; the venv is at
   `/home/user/openflowsheet/.venv`, run from this worktree with `PYTHONPATH=$PWD/src`).

**Out of scope.** Any dynamic code; changing frozen interfaces (plan §2.1) or schemas; re-opening D1–D4 or A1
rulings; v0.3 scope.

**Agent rules.** Context cap about 120k; at the cap commit, write a handoff of ≤ 30 lines to
`docs/briefs/C1-handoff.md`, stop. Report ≤ 150 words. Defensible choices: one `DECISION:` line each, logged in
`docs/C1_DECISIONS.md`. Questions only Frank can answer: `docs/FRANK_QUESTIONS.md` with your default.
