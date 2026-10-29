# ADR 0050 — The binding package: record-source bases for IAPWS-95, CoolProp and Wilson, basis-generic routing models, and `syn001.column` in flowsheets (package S11)

**Status:** **Proposed, 2026-10-26** (design lane, `architect`; register R-800…R-812). It becomes **Accepted** when:
- S11's evidence manifest is `tested`, with gates G1–G8 of the design note passing;
- the `reviewer` has passed the work orders against the design note.

**Implemented, tested (2026-10-28, WO-I2):** `evidence/S11/01e72ca464dcb68c489e235d3d5446d450e109e1/manifest.json` is `status: tested`, 123 of 126
checks: S11.A01–A93 and A24′, G1–G7 and G9–G13. G8 (the full gate, CI on both architectures and the
cross-architecture comparisons) and the `reviewer` pass are outstanding, so the status stays **Proposed**.

**Amended 2026-10-27 by the design lane's rulings on S11's build decisions** (`docs/reviews/S11-rulings.md`,
R-830…R-842): a class of provider-identity record files for T08.A32 (R-830); a one-sided five-point derivative
witness at absent-component zero columns on Wilson, R-281 not extended (R-831); W27v3-R09 (R-832); kernel fix C3-1
accepted (R-833); S11.A46 restated with a fixed 1e-5 at the two near-top states (R-834); S11.A12 restated to ≤ 2 ulp
(R-835); A68 and A77(iii) restated (R-836); "all existing W27 tests pass unchanged" read through `v2_binder()`
(R-837); tracks B, C, D and A's decisions (R-838…R-841); the identity gate's `VOLATILE` revision ids (R-842).

**Date:** 2026-10-26
**Author:** design lane (`architect`), brief `docs/briefs/S11-binding-design.md`.
**Normative text:** `docs/derivations/S11-design.md`. W27 registration version 3 is
`docs/derivations/W27-registration-v3.md`, which WO-A4 transcribes from the design note's §4.10.
**Decided by Frank (2026-10-26):** "I want the binding package". This supersedes the "library only for now" defaults
within S11's scope.

**Changes a frozen shape:** `SELECTABLE_BASES`' element type `ComponentBasis` gains the field `record_source`, and
the sequence lists every concrete basis (127). W27-R63 and T08.A20 read this shape.

**Amends:**
- ADR 0034 D8. `component_set.record_source` selects a basis from a registry of five record sources. Every
  unregistered value still selects SYN-001.
- ADR 0049 C4. R-781's deferred P1–P3 check is made at bind for every Wilson basis.

**Supersedes:**
- the library-only clauses of ADR 0045 (S05), ADR 0046 D9 (S07) and ADR 0047 D10–D11 (S10) — but not ADR 0047 D7,
  Q-F3, on shipping the records;
- S05 A25 and Q-8, S10 A27, S10-C design §7 Q1 and Q3, R-709's flowsheet clause, and Frank's Q-F2 default. R-810
  records each one.

No `Protocol`, schema, quantity kind, check category or tolerance changes. Every revision that binds today binds and
solves bit-identically (gate G1).

**Affected requirements:** D08 (provider conformance in consumers), U02 and U04 (unsupported rows), T08.A20 (the
providers axis), W27-R63 (the route reading), R01 (cases).
**Affected packages:** S11 implements it. S05, S07, S10 and S10-C providers are consumed byte-unchanged. S02, S06 and
S08 are consumed through `links=None`, unchanged.

## Context

S05, S07 and S10 shipped three property providers at library level. Selection by `record_source` knew only
`pr-c1-v1`'s records. `MODEL_BASES` admitted each model on exactly one basis. The S02/S06 column was library-only,
and so its S06 inverse rows formed `F`, `ν*` and `π*` from pinned inlets that do not exist in a flowsheet (S06 §15
Q7). R-781 deferred the Wilson premises check to this package.

## Decisions

**D1. Selection by registered record source; no schema change.** The registry:

| record source | provider |
| --- | --- |
| `benchmarks/m01/components.yaml` | `pr-c1-v1` |
| `benchmarks/s05/components.yaml` (new) | `iapws95-v1` |
| `benchmarks/s10/records.yaml` | `wilson-ig-v1` |
| `benchmarks/s07/components.yaml` (new, generated) | `coolprop-heos-v1`, one fluid: the revision's single component |
| anything else | `syn001` |

A CoolProp revision with other than one admitted component is `components_unsupported`.

**D2. One `SELECTABLE_BASES` entry per concrete basis,** in a fixed order: SYN-001, C1, IAPWS-95, Wilson, then the
123 CoolProp fluids in the S07 table's order.

**D3. Admission stays an identity table.** `MODEL_BASES` keeps its shape.
- The three routing models (`syn001.feed_source`, `syn001.product_sink`, `syn001.stream_splitter`) bind on every
  basis except C1. Their manifests are built from the bound provider; SYN-001's bytes do not change.
- `syn001.column` binds on `syn001` and `wilson-ig-v1`.
- No other `syn001.*` or `c1.*` model is admitted on a new basis, because each one encodes its own provider's
  physics. Every refused pair is `model_unsupported(<id>)` with a reason.

**D4. Bind-time basis preconditions, typed:**
- `basis_unavailable(coolprop-heos-v1)` when the extra is not importable;
- `basis_unavailable(wilson-ig-v1)` when the repository-only records are absent (a wheel; R-706, Q-F3);
- `basis_premises_unmet(wilson-ig-v1)` when P1–P3 fail on the records' T domain. The check is closed form: the
  endpoints and the real roots of each premise's critical-point cubic.

**D5. The verifier** constructs providers from its own table by basis (`fresh_provider(basis)`). It resolves one of
three property forms: SYN-001's and `pr-c1-v1`'s, both unchanged, and a declared-phase mixture-`h` form for the new
bases. It never asks a non-SYN-001 provider for `lnK` or `h_<c>`.

**D6. `syn001.column` is embedded.**
- The flowsheet face is the standalone declaration. The inlet pin rows become link rows to the feed streams, and link
  rows tie the products to the outlet streams. The unit owns every internal column.
- `evaluate` runs `solve_column` on the inlet states, and the EO start reads the internal values from
  `UnitEvaluation.owned` (new, defaulted).
- The stage splits reach the region solver as in the standalone solve.
- A column requires `T05b-phase-contract-v2`.

**D7. S06 §15 Q7.** In a flowsheet, purity uses `F_ref = 1 mol/s` in place of `F`. Recovery gains a definition row
`F_ref·n_c − w·F_c(x)` and a column `w`. Then `π* = x*` and `ν* = r*` are constants of the document, every slot is
`v − p`, and the roots equal the standalone roots.

**D8. The cascade** is bound through the column with `top` and `bottom` connected. `syn001.cascade` stays
library-only and is refused with that hint.

**D9. W27 registration version 3:**
- provider rows `iapws95-v1 → iapws95`, `wilson-ig-v1 → activity_coefficient`, `coolprop-heos-v1 → pure_helmholtz`
  (a new method that matches no case);
- routes keyed by `(provider_id, record_source, components)`, with a generic records line;
- `syn001.column` with function `null`.

Versions 1 and 2 stay byte-identical.

**D10.** `pr-lib-v1` stays library-only (R-615).

## Alternatives considered

- **A `property_basis` schema member.** It changes a frozen schema, and two sources of truth would have to agree with
  the still-required `record_source`.
- **URI-like `record_source` values.** They break the field's meaning.
- **Selection by the record file's content.** The revision's hash would not cover the bytes it reads.
- **Basis families in `SELECTABLE_BASES`, or one union route per provider.** The selectable entry would no longer be
  what a revision binds, and W27 would over-claim multi-fluid CoolProp cases.
- **Capability-based admission, or per-basis namesake families.** Capability flags cannot see physical assumptions
  (the SYN-001 pump's isothermal-equals-isentropic). Namesakes grow N×M.
- **The column as an implicit black-box block.** Its value would depend on the inner warm start, so it would not be
  a function of `x` (ADR 0008 D1).
- **`F`/`F_c` frozen from the traversal.** That gives the wrong root under recycle, with constants that depend on the
  solve path.
- **Dimensionless slot rows.** They need a new row kind.
- **Editing W27 v2.** It moves a registered file's SHA-256, which v2 coverage records carry.

## Consequences

- **C1.** Revisions can select IAPWS-95, any of 123 CoolProp fluids, or Wilson's methanol–ethanol–water records.
  Pure-fluid bases bind routing models only, until S11b (pure-fluid units with an ADR on two-phase pure-fluid streams
  under `nTP-v1`). Wilson binds routing models and the column.
- **C2.** Distillation columns (and absorbers or strippers through `none` ends) enter flowsheets on SYN-001 and
  Wilson, certified by the verifier: material, energy, specification and stage-admissibility checks, plus Wilson
  liquid stability.
- **C3.** In a wheel, Wilson revisions are refused `basis_unavailable` until Frank decides Q-F3. This is a default
  open to Frank (R-811).
- **C4.** The next release's W27 run selects version 3.
- **C5.** `LIBRARY_ONLY_PROVIDERS == {"pr-lib-v1": "S04"}`. The envelope gains L-S11-1…3 and L-COL-1…8. U02 and U04
  are rewritten. No earlier harvest entry is edited.

## Acceptance evidence

- Gates G1–G8 of `docs/derivations/S11-design.md` §6. G1 is
  `S11-IDENTITY PASS n=<N> changed=[]`, and the S08 and S10-C identity lines reproduce.
- `evidence/S11/<commit>/manifest.json` at `tested`.
- One `reviewer` pass.
