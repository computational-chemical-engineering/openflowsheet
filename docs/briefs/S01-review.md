# S01 — independent review and ruling round (design lane, `reviewer`)

Branch `wp/S01` (worktree `/home/user/ofs-s01`), 16 commits on `main` `3c10e97`, ~8.2k lines. This is the package's
single `reviewer` pass (CLAUDE.md agent budget); it also carries the batched design-lane questions.

## The question
1. Does the implementation meet `docs/derivations/S01-spec.md` (A01–A20), and does each test actually verify what its
   assertion claims (mutation-minded)? Residual/Jacobian consistency, phase logic, scaling, continuation identity —
   CLAUDE.md requires a design-lane review for these.
2. Rule on the seven open questions in `docs/S01_DECISIONS.md:77-83` (WO-1: refusal outcome vs `SolveOutcome`; R7
   with all inlets dormant; R5 vs code R-007; phase of `top`/`bottom` inlets. WO-2: A04/A06 10× margin measured
   2.2×/8.7×; A05 C1 9.77e-7 K vs 1e-7; A10 FD floor 3.4e-8 at C2's Q columns vs 1e-8, 5.9e-11 with a D_x-scaled
   step). For each: is the spec right and the code wrong, or the registered value wrong? A tolerance may change only
   with a derivation of why the registered one was wrong — never to pass. Record rulings as a dated spec amendment
   and register entries **R-510…R-519**.

## Facts with anchors
- Spec `docs/derivations/S01-spec.md` (§10 assertions :184-218, §12 WOs :226-245, §13 manifest :246-253).
- Reference `docs/derivations/scripts/s01_reference.py` + `.json` (153 claims, mpmath 50 digits).
- Code `src/openflowsheet/models/syn001/cascade.py` (WO-1), `cascade_solve.py` (WO-2/3).
- Tests `tests/test_s01_cascade_wo1.py` (69), `_wo2.py` (39 + 4 strict xfail), `_wo3.py` (9).
- Manifest `evidence/S01/ea125486b10476de107e8a37ba05c56718cef1d8/manifest.json` (`implemented`; 20/26 pass; gate
  check `unsupported`). Generator `scripts/s01_evidence_manifest.py`.
- Decisions/measurements `docs/S01_DECISIONS.md`; WO handoffs `docs/briefs/S01-WO*-handoff.md` if present.
- Env: from the worktree, `PYTHONPATH=$PWD/src /home/user/openflowsheet/.venv/bin/python -m pytest -q tests/test_s01_*.py`.

## Exit test
`docs/reviews/S01-review.md`: findings classified must-fix / should-fix / note, each with file:line and a concrete
failure scenario; the seven rulings; the work order(s) the build lane must do before `tested`. Spec amendment +
register entries committed. You may write adversarial tests yourself. Do NOT set `reviewed` in the manifest (that
needs human sign-off) and do not fix production code yourself.

## Out of scope
S02 conventions; new methods; re-deriving the whole spec.

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/S01-review-handoff.md`, stop. Report ≤ 150 words.
