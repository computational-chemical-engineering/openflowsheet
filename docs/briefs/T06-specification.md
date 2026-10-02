# Brief — T06 specification: the v0.1 case corpus, robustness ensemble, reference comparisons and verifier breadth

**To:** `specifier` (design lane). **From:** build lane, 2026-09-25. **Branch:** `wp/T06` (from `main`
at `63364f8`, `wp/T06-refs` merged: `65d4d18`).
**Deliverable:** the T06 specification `docs/derivations/T06-corpus-spec.md` (or split into parts if
you judge one document too large — say so), with registered cases, the sampling law, budgets,
tolerances, preregistered classifications and numbered falsifiable assertions; an ADR for any
decision a later session could plausibly undo (0014 is the next free number); register entries;
machine-readable reference values from a twin where values are computable independently (extend or
add a script under `docs/derivations/scripts/`, `--check`, byte-reproducible `--emit`, no
`process_runtime`/`benchmarks` import); and a build-lane **work order in phases** (measure-first
items, then implementation chunks each with inertness proof). Write no production code; do not
commit.

## 1. The package (plan v1.2 §4.3, row T06 — binding)

> T06 | T04, T05: strengthen rank/conditioning and verifier; register 30+ distinct cases, robustness
> generators, eight reference comparisons. Start reference acquisition after P03. | Correct verdicts;
> 20×20 registered ensemble; retained failures; 95% nominal target; numerical and cost reports; no
> false verification. | NUM/MOD | Design / Build

Plan §4.3 note: "T06: SYN-001 r-variants are one recycle case, not three (§3.2). NET-07, a thermally
coupled recycle, is mandatory so that at least one registered recycle has genuine composition–energy
coupling." **Read plan §6 (§6.1–§6.5, `docs/implementation-plan.md:363–405`) in full** — it fixes the
seven case classes (STR-01–06, STA-01–04, NUM-01–06, THM-01–06, NET-01–07, ADV-01–06, VER-01–05), the
generator (Uniform[−0.2, 0.2] on scaled free coordinates about a registered initializer, domain
rejection, retry cap, zero-flow parameterizations, saved hashes/seeds/states/rejections; no hidden
converged answer), nominal vs stress profiles, clustered uncertainty, budgets and time ceilings
registered before scoring, §6.3's rank-evidence recipe (and its two mandatory matrices: a badly
conditioned upper-triangular with innocuous diagonal; `x² = 0`), and §6.4's reference rules
(same semantics, preregistered tolerances, `AGREE`/`DISAGREE`/`NOT_COMPARABLE` with reasons, access vs
science separated, no tuning). Release gates V16, V18, V20 and requirements D05, D11, D14, D19, D20,
A04, A08, A09 in `docs/requirements.yaml` (read their minimum evidence).

## 2. Frank's standing directives (2026-09-25)

"As little limitations as possible"; "robustness is the important thing — if a method cannot solve a
hard case and the solver then switches to another method this is also fine" (recorded, deterministic
fallbacks; never a relaxed check). He agreed every default currently in force (T05 Q2/Q3/Q7/Q8/Q9;
T05b §18 Q9; K04-F9 §12 Q1; design Q-D, Q-G) — `docs/T05_DECISIONS.md`, last entry.

## 3. What exists (read; do not re-derive)

- **Registry** `benchmarks/registry.yaml`: 29 cases — 25 family `SYN-001`, 4 family `SYN-001-UL`
  (T05's C1–C3X); 12 in the success denominator (measured on `wp/T06`). Many more *registered
  fixtures* live only in tests and specs: T02 (A02 family scan of 180 runs, oscillatory cases), T03
  (PHS cases, OFF-B), T04 (HOM-01…05, PTC seeds, the basin study), T05 (56 unit cases, C1–C3X), T05b
  (SC-1…4, NP-1…3, NP-G, NP-GC, DZ-1…12, CH-*), K04-F9 (A02 family under ADR 0013). Decide which of
  these become corpus cases and in which class, without near-duplicates (§6.1's rule).
- **NET-07 candidate:** T05's C3 (spec `docs/derivations/T05-unit-models-spec.md` §11.3: tear-map
  Jacobian `∂T'/∂n = (−3.120, 4.666, 9.737) K per mol/s`, spectral radius 0.527; its honest limit — its
  fixed point reduces to one scalar equation). T05 registered it as a candidate; T06 decides.
- **Reference environments** (`docs/reference-environments.md`, merged from `wp/T06-refs`): DWSIM
  9.0.5 and IDAES 2.13.0 build reproducibly and run headless; the representability table for §6.4's
  eight fixtures; licences (IDAES's HSL MA27 is not open source; reference tools only, never
  distributed); **§7's open design decisions** (Poynting factor, DWSIM's latent-heat offset, recycle
  tolerance mapping, …) are yours to decide.
- **Verifier state:** K04 (screen, certificate, [A08] rank screen), T04 (bound declaration), T05
  (per-model table, `verify_revision`), T05b/ADR 0012–0013 (saturation band, zero-flow regularity,
  projection). One T05b hand-on bears on D20/A08: `onenormest` makes `rcond_1`,
  `inverse_one_norm_estimate` and the solution-error bound depend on numpy's global RNG (C2's bound
  3.0e-15…3.9e-15 and C3's 3.0e-9…3.4e-9 over 20 seeds; no R0 field moves) — rule on determinism.
- **Solver state:** contracts v1 and v2 (ADR 0005, ADR 0012), recovery edges 1–3, homotopy, PTC
  (experimental, ADR 0010), recorded fallbacks. Registered limitations: T05b §18 Q9 (a zero-duty flash
  fed exactly at its dew point: `UNVERIFIED`).
- **Identity:** K05 structural hash `4ce030ca…` and the identity document with keys `t02`…`t05b`; any
  new corpus/ensemble identity goes under a new key and must not move the existing ones.

## 4. Constraints

SYN-001 and every registered T02–T05b result stay as registered unless you say why (bit-identity
evidence as in T05/T05b). R-016 (verifier independence). No relaxed check, no narrowed denominator,
no case moved outside the envelope without an explicit support-matrix change (§6.2). The gate must
not depend on external tools (DWSIM/IDAES comparisons run outside `scripts/check.sh`; their recorded
outputs are evidence, with hashes). Budgets and time ceilings registered **before** scoring. The
95% nominal target is a gate to measure, not a number to engineer toward — if the measured rate is
below it, the package reports it failed (CLAUDE.md "Scientific conduct").

## 5. Genuinely open (decide these)

1. The corpus: the ≥30 distinct counted cases by class, each with its failure mechanism, revision
   or fixture, expected outcome and denominator membership; which existing fixtures are promoted;
   which new cases must be built (and whether any needs a new unit model or capability — flag it).
2. NET-07: C3 or another case.
3. The generator (A04): coordinates, scales, domain rejection, retry cap, zero-flow handling, the RNG
   and its recording; the 20 eligible cases × 20 starts; nominal vs stress profiles.
4. Scoring: success definition (converged **and** `VERIFIED`?), per-case success, clustered
   uncertainty, the 95% nominal gate's exact computation, retained-failure classification, and cost
   reports (budgets, time ceilings by machine class, cache conditions).
5. Rank/verifier breadth (A08, D05, D14): §6.3's diagnostics across the ensemble, VER-01–05, the two
   mandatory matrices, determinism of the estimates.
6. The eight reference comparisons (D19): which fixtures, which tool(s), matched semantics, the §7
   decisions, preregistered tolerances, verdict mechanics (the `verdict` agent issues verdicts on the
   measured evidence later).
7. Replay/reproducibility of the ensemble (D20) and its identity key.
8. Phasing: what the build lane can do in parallel; where `architect` is needed for software design
   (an ensemble runner, a reference-comparison harness) — say so with the question.

## 6. How it will be verified

The gate (3141 green at `65d4d18`), your assertions, the ensemble's measured rates against the
preregistered gate, reference verdicts by `verdict`, CI on x86-64 and aarch64, `reviewer`, evidence
`evidence/T06/<commit>/manifest.json`.

## 7. Out of scope

T07 (application/API surfaces), T08 (release evidence, real chemistry), performance at plant size.
