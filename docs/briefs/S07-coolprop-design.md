# S07 — CoolProp as an optional external property provider, pure fluids first (design lane, `specifier`)

**Question.** Write ADR 0046 and the S07 spec (derivation-level contract + test specification with numbered falsifiable
assertions, registered states, tolerances, a reference generator plan, and work orders) for a provider that evaluates
pure-fluid properties through CoolProp. Frank queued it 2026-10-23 (`docs/CLOUD_WORK.md` S07 row; all work now local).

**Settled (Frank / session recommendation he accepted, 2026-10-23):**
- CoolProp is called only as a Helmholtz evaluator at (T, ρ) (its low-level `AbstractState`, HEOS backend) with its analytic
  pure-fluid partial derivatives; the project's own phase logic, phase-attempt controller, retry/recovery rules and exact-input
  caches stay in control (blueprint §6.1, D08, D10). CoolProp's own flash routines are not used on the exact path.
- One pinned CoolProp version, as an **optional** dependency (an extra, not in the default wheel's requirements); the project
  does not redistribute CoolProp's fluid data. Rights: CoolProp is MIT; its EOS coefficients come from papers/REFPROP (see
  `docs/l01-rights-check.md` RC-01/RC-02) — the ADR must state why runtime use without redistribution is acceptable or flag it.
- Bit-identity must hold on both CI architectures (x86-64 `ubuntu-latest`, `ubuntu-24.04-arm`) for the registered values, or
  the spec states the measured cross-architecture tolerance and why.
- Cross-checks: against S05 `iapws95-v1` for water (`src/openflowsheet/thermo/iapws95.py`, `docs/derivations/S05-IAPWS95-spec.md`)
  and against the S04 `pr-lib-v1` records where meaningful (ideal-gas parts).
- Mixtures out of scope until measured (composition derivatives would need declared, audited finite differences, blueprint §6.1/§179).
- Binding into flowsheets (a selectable basis without a records file, unit models, W27 v2 mapping, support-matrix row, envelope):
  Frank answered S05 Q-8 "library only for now; binding planned later together with S07". So S07 may either stay library-only
  or design the shared records-less basis key for both S05 and S07 — decide which, keep S07's first delivery small, and list the
  binding package as a follow-on if not included.

**Pattern to follow.** S05 is the closest precedent (ADR 0045, spec, `s05_reference.py`, the evidence manifest, the packaging hold
and its later inversion R-594 → R-616/R-617). Existing providers: `src/openflowsheet/thermo/{pr_c1,pr_lib,iapws95,cache}.py`.
CoolProp is not installed in `.venv` (`ModuleNotFoundError`); a pinned version must be added (requirements.lock is pinned; say how
the extra enters the lock and CI).

**Open for you to decide:** the initial fluid list (justify from OpenIDAES-450 development-half needs:
`benchmarks/l01/` projection and `docs/derivations/L01-spec.md` §6.3 show what blocks cases; CoolProp fluids beyond water);
the state variables offered; domain per fluid; derivative orders; how the provider's identity (`implementation_sha256`,
`data_sha256`) works when the data lives in a third-party package; the version-pin/identity rule.

**Deliverable.** On branch `wp/S07` (worktree `.claude/worktrees/s07` from `main`): ADR 0046 (Proposed), `docs/derivations/S07-spec.md`,
register entries (next free R-numbers, grep `^## R-6`), questions for Frank (if any) in `docs/FRANK_QUESTIONS.md` in plain words
with defaults, work orders sized ≤ ~100k context each. Docs only; no production code. Commit, push the branch, do not merge.
Context cap ~150k. Report ≤150 words.
