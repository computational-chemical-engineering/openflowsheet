# C10 — IAPWS-95 as a planned v0.3 property method: ADR, derivation and test specification (design lane, `specifier`)

Branch `wp/C10` from `main`. Source: `docs/CLOUD_WORK.md` C10; Frank's answer L01-Q3 (`docs/FRANK_QUESTIONS.md:17`):
IAPWS-95 is the next property method, **a planned v0.3 addition with its own ADR (design lane first), not benchmark
tuning.** Register numbering: **R-585…R-594**. ADR number: **0045**. Package id: name it under plan letters (an S/R id per
R-565 / D1 Q6 — propose `S05` with a DECISION line) so it can carry a `tested` manifest.

## The question
Specify a pure-water property provider implementing the IAPWS-95 formulation (Helmholtz energy, both phases, saturation)
so that a build-lane engineer can implement it on the existing provider contract without further scientific choices:
the use case, affected requirements, acceptance evidence (the ADR); the derivation of every property the provider must
return from φ(δ, τ) (p, h, s, c_p, fugacity/φ, derivatives the solver needs, saturation by Maxwell/phase equilibrium);
domain and refusals; reference state and its relation to the existing conventions; and numbered falsifiable assertions
against **independent expectations**.

## Facts with anchors
- Provider contract: `src/openflowsheet/thermo/__init__.py` (`PropertyRequest`, `PropertyResult`, `FlashRequest`,
  `FlashResult`, `PropertyCapabilities`, `StreamState`); providers to pattern on: `thermo/pr_c1.py` (analytic implicit
  derivatives, typed refusals, implementation/data hashes, ADR 0026), `thermo/pr_lib.py` (S04, ADR 0043),
  `thermo/syn001.py`. Reference conventions: ADR 0001 D5 (`docs/adr/0001-state-units-zero-flow.md`), `PR-C1-ref-v1`
  (ADR 0026); state definition `nTP-v1`. Exact property caches key on exact canonical inputs (CLAUDE.md).
- Why it matters: water is the most frequent unavailable component on the OpenIDAES-450 development half (L01 spec
  `docs/derivations/L01-spec.md` §3; the iapws95 method is registered in W27's `package_methods`). Development half only;
  never cite held-out cases (C2 split).
- Independent expectations available offline-ish: the IAPWS R6-95(2018) release's verification tables (Tables 6–8:
  ideal and residual parts of φ and derivatives at two state points; single-phase and saturation check values). The
  session's proxy may refuse iapws.org — then use what is reachable: CoolProp 8.0.0 is installed in
  `/home/user/venv-l01-sources` (its Water fluid file carries the IAPWS-95 coefficients with citations; MIT); PyPI is
  reachable through the proxy, so the `iapws` package can be installed into a scratch venv as a second independent
  implementation. Never into the project `.venv`. Transcribed coefficients need a cited source and a hash; the
  reference generator must be independent of the future `src/` module (pattern: `docs/derivations/scripts/*_reference.py`,
  mpmath at 50 digits where useful).
- Rights: IAPWS releases and coefficient transcription — record the rights basis per source the same way C12 does
  (`docs/l01-rights-check.md`); if terms cannot be read from this session, mark them `unresolved` and say the records
  must not ship before the check (Frank's L01-Q4 rule applies by analogy).

## Exit test
ADR 0045 (Proposed) + `docs/derivations/S05-IAPWS95-spec.md` (derivation, domain, refusals, reference state, assertions
`S05.A01…` each with an independent expectation and justified tolerance, work orders ~120k each, manifest check list,
non-claims) + reference generator with `--check` and its data, register entries, `DECISION:` lines in
`docs/C10_DECISIONS.md`, Frank questions in `docs/FRANK_QUESTIONS.md`. No production code.

## Out of scope
Mixtures with water (electrolytes, NaCl), IAPWS-IF97, transport properties, binding the provider into flowsheets or W27
exposure (later packages).

## Agent rules
Context cap ~120k; at the cap commit, write a ≤ 30-line handoff `docs/briefs/C10-handoff.md`, stop. Report ≤ 150 words.
