# S11 design: the binding package — library-only property bases and the column in flowsheets

**Status:** design lane (`architect`), 2026-10-26. Branch `wp/S11` from `main` `8c34ecb0`.
**Brief:** `docs/briefs/S11-binding-design.md`; facts: `docs/briefs/S11-binding-recon.md` (the recon digest, cited as
"digest §n").
**Records:** ADR 0050 (`docs/adr/0050-s11-binding-package.md`, Proposed); register R-800…R-812.
**Normative for:** what a revision writes to select each property basis; `ComponentBasis` and `SELECTABLE_BASES`;
the admission of unit models per basis; the bind-time basis preconditions; the verifier's per-basis provider and
property forms; `syn001.column` as a flowsheet unit, including S06 §15 Q7's ruling on `F`, `F_c`, `ν*`, `π*`;
W27 registration version 3; the support-envelope rows. Everything here stands alone; the brief is not needed to
implement it.

---

## 0. The decisions in one screen

1. **No schema change.** A revision selects a basis by `component_set.record_source`, as ADR 0034 D8 does for
   `pr-c1-v1`, from a registry of record sources. Two new ComponentRecord files are added so that every basis has
   one: `benchmarks/s05/components.yaml` (water) and `benchmarks/s07/components.yaml` (every admitted CoolProp fluid,
   generated). Wilson uses its existing `benchmarks/s10/records.yaml`. A CoolProp revision names its fluid as its
   **single** component. Every unregistered value still selects SYN-001, exactly as today. (§4.1, D1)
2. **`ComponentBasis` gains `record_source`.** `SELECTABLE_BASES` lists every concrete basis, 127 in all: SYN-001,
   C1, IAPWS-95, Wilson (real records), then one per admitted CoolProp fluid (123) in the S07 table's order. (§4.2, D2)
3. **Admission stays an identity table.** `MODEL_BASES` is still the only admission table (model → provider ids).
   Day one: the 13 `syn001.*` and 9 `c1.*` models are unchanged. The three routing models (`syn001.feed_source`,
   `syn001.product_sink`, `syn001.stream_splitter`), which hold no provider, bind on every basis except C1, with
   manifests built from the bound provider (SYN-001's bytes do not change). `syn001.column` binds on `syn001` and
   `wilson-ig-v1`. Every other pair is refused `model_unsupported(<id>)` with a reason. No `syn001.*` or `c1.*`
   thermal unit is reused on a new basis, because each one encodes its own provider's physics. (§4.4, D3)
4. **Bind-time basis preconditions.** CoolProp's optional extra must be importable, and Wilson's records must be
   present. Wilson's records must also satisfy the column theorem's premises P1–P3, checked in closed form; this
   closes R-781. Each failure is typed. (§4.3, D4)
5. **The verifier gets its own table by basis**, `fresh_provider(basis)`, and a third property form beside SYN-001's
   and `pr-c1-v1`'s: mixture `h` in a stream's declared phase, with an admissibility rule per basis. It never asks a
   non-SYN-001 provider for `lnK` or `h_<c>`. (§4.6, D5)
6. **The column is embedded, not wrapped.** In a flowsheet, `syn001.column` contributes S02/S06's own rows. Its inlet
   pin rows become link rows to the feed streams, and link rows tie its two products to the outlet streams. It owns
   every internal column. `evaluate` runs the standalone `solve_column` on the inlet states, and the EO start takes
   the internal values from it through a new `UnitEvaluation.owned`. Its stage splits reach the region solver as
   they do in the standalone solve. (§4.7, D6)
7. **S06 Q7 ruling.** In a flowsheet the feed is solved, so `F` and `F_c` are not constants. Purity uses a fixed
   reference flow `F_ref = 1 mol/s` in place of `F`. Recovery gains a definition row `F_ref·n_c − w·F_c(x)` with its
   own column `w`. Every pinned parameter is then a constant of the document, and every slot keeps the `v − p` form
   that edge 3 continues on. The roots are the standalone roots. (§4.7.4, D7)
8. **The cascade is bound through the column**, with `top` and `bottom` connected (condenser `none`, reboiler
   `none`; S02 §1). `syn001.cascade` stays library-only and is refused with a hint. (D8)
9. **W27 registration version 3.** Three provider rows are added: `iapws95-v1 → iapws95` (S05 F-3),
   `wilson-ig-v1 → activity_coefficient`, and `coolprop-heos-v1 → pure_helmholtz` (a new method that matches no
   case). Routes are keyed by `(provider_id, record_source, components)`, with a generic records line, and
   `syn001.column` is registered with function `null`. Versions 1 and 2 stay byte-identical. (§4.10, D9)
10. **Out of S11, with explicit refusals:** pure-fluid thermal units (follow-on S11b, which needs an ADR on two-phase
    pure-fluid streams under `nTP-v1`); γ–φ EO faces for the K02/T05 units (S11c); `pr-lib-v1` (R-615 stands);
    NRTL/UNIQUAC/LLE. (D10, §7)

---

## 1. Problem and scope

**Build.** Make `iapws95-v1`, `coolprop-heos-v1` and `wilson-ig-v1` selectable in process revisions, so that the
binder, the solver and the verifier take them. Bind `syn001.column` (S02/S06/S08/S10-C) into `MODEL_BUILDERS` on
SYN-001 and Wilson, with its support-envelope rows. Do the admission-time checks deferred to "the binding package".

**In scope:** the basis registry and selection; `ComponentBasis`/`SELECTABLE_BASES`; `basis_provider` and the
verifier's `fresh_provider`; the routing models on the new bases; bind-time preconditions (availability, P1–P3);
the verifier's per-basis forms; the column's flowsheet unit, binding, orchestration (traversal, EO start, staged
splits) and verifier checks; W27 registration v3; envelope, T08, `LIBRARY_ONLY_PROVIDERS`, the harvest; the identity
gate; the disposition of every digest §6 item (§4.13).

**Out of scope:** NRTL/UNIQUAC/LLE (an interface ADR first, S10 spec); Helmholtz mixtures; S07b cryogenic liquids;
the methanol+ethanol refit; any change to a registered numerical result; GUI/web; any change under `thermo/` to an
existing provider module (their `implementation_sha256` hash the module bytes); pure-fluid thermal units (S11b);
γ–φ EO faces for the units other than the column (S11c); `pr-lib-v1`; user-supplied record files; side draws,
pump-arounds and efficiencies; the registration of the column function against the OpenIDAES-450 archive
(workstation).

---

## 2. Constraints and invariants

### 2.1 Conventions

- **Units and sign:** SI. `Q > 0` into a stage or unit (ADR 0001 D4.1); a condenser duty is negative.
- **State:** `nTP-v1` (ADR 0001 D2). A component vector is indexed by the basis' component order. A declared
  component list must be a permutation of `basis.components`, and `canonical_components` is unchanged.
- **Stages** `j = 1..N`, top to bottom. `N` counts the condenser and the reboiler (S02 §1).
- **Reference conventions:** streams of different conventions never mix (ADR 0001 D5.2). One revision has one basis,
  so this holds by construction.
- **Row ids, column ids and kinds:** existing S01/S02/S06 ids are reused unchanged. New ids are listed in §4.7.

### 2.2 What must stay bit-exact, and what may move

- **Bit-exact:** every revision that binds today binds to the same declaration, with the same `ProblemSpec` ids,
  parameters, `float.hex` values and hints. Every registered solve gives byte-identical results. S08's and S10-C's
  identity lines reproduce: `S08-IDENTITY PASS n=52 changed=[S02.P1] p1_stage_a=EQUAL` and
  `S10C-IDENTITY PASS n=858 changed=[]`. The SYN-001 manifests of the three routing models are byte-identical. The
  W27 v1 and v2 outputs on all registered states are byte-identical. The served MCP tool list digest does not move,
  because no served schema changes.
- **May move, by design:** the tests whose assertions S11 reverses (the list is in §8.3); `SELECTABLE_BASES`;
  `MODEL_BASES`/`MODEL_BUILDERS` (one model, `syn001.column`, is added); the envelope and the support matrix;
  `HARVEST_SIZE`, by S11's own appended harvest only.
- **Tolerance, not bits:** Wilson and CoolProp results across architectures (as S07 and S10-C).
- **Registered results that are not moved:** no earlier harvest entry is edited (HG(b), R-617), and no file under
  `thermo/` that existed before S11 is edited.

### 2.3 Frozen interfaces

No `Protocol`, schema, quantity kind, check category or `KIND_TOLERANCE` entry changes. `SELECTABLE_BASES`' element
type gains a field. That is the frozen-shape change that ADR 0050 records (W27-R63 and T08.A20 read it).
`UnitEvaluation` gains one defaulted field; it is not on the frozen list. `orchestrator.splits.lifted_splits` gains
one optional argument.

### 2.4 Parallel and device contract

Single process, no GPU. A provider is constructed fresh per binding and per verification. CoolProp's provider is
`not_thread_safe`, so it is never shared between a binding and a verifier.

---

## 3. Decisions and rejected alternatives

**D1 (R-800). Selection by registered record source; no schema change.** A ComponentRecords file is what
`record_source` already means ("Path to the file holding the referenced ComponentRecords"). Every basis needs molar
masses (`unit-conversion-v2`'s mass basis), which records carry, and the provider choice follows from the records
because method-specific parameters (Wilson Λ, PR k_ij) live in them.
*Rejected:*
- *An optional `component_set.property_basis` member.* It changes a frozen schema, and it does not remove
  `record_source`, which is required, so two sources of truth would have to agree.
- *URI-like `record_source` values* (`provider:coolprop-heos-v1`). They break the field's stated meaning.
- *Selection by the record file's content* (its declared convention). It reads an arbitrary file whose bytes the
  revision's hash does not cover, so replay identity is lost; user records are a later package.

**D2 (R-801). One `SELECTABLE_BASES` entry per concrete basis.** `component_basis(document)` returns one of them, by
identity. This keeps the invariant that W27-R63 and T08 read: *the entries are exactly what selection can return*.
*Rejected:*
- *Basis families* (one CoolProp entry with 123 components and "one per revision"). The selectable entry would
  differ from the basis a revision binds.
- *A union route per provider.* It would claim that a multi-fluid case is served by CoolProp.

**D3 (R-802). Admission by identity in `MODEL_BASES`; routing models generic; no thermal-unit reuse.** Capabilities
cannot see a model's physical assumptions. S10-C D1 showed this for equilibrium forms, and the SYN-001 pump's
"isentropic = isothermal enthalpy rise" holds only because SYN-001's liquid entropy does not depend on P. For Wilson
(h^L independent of P, no v) that assumption gives `W = 0`, and nothing in a capability flag says so. The C1 units
carry B16's NH3/τ_dew vapour rule. So no `syn001.*` or `c1.*` thermal unit is admitted on a new basis. The three
routing models hold no provider. They become basis-generic, with only their manifest fields taken from the bound
provider.
*Rejected:*
- *Capability-based automatic admission* (above).
- *Per-basis namesake families* (`wilson.feed_source`, …). That is N×M duplication for every future basis; the C1
  family keeps its namesakes because its physics differs.
- *Admitting syn001 thermal units on Wilson now.* Their EO faces read `lnK` and `h_<c>`, which the S10-C tripwire
  refuses; migrating them is S11c's design pass.

**D4 (R-803). Basis preconditions at bind, typed.**
- CoolProp: `importlib.util.find_spec("CoolProp")` must not be `None`. Version and gitrevision mismatches remain the
  provider guard's, at the first evaluation.
- Wilson: the records must load, and P1–P3 must hold over the records' T domain, decided in closed form (§4.3).
- *Rejected:* pinning the records' SHA-256 (R-781 rejected it: refits and test copies); a grid-only check (R-781: not
  a proof); a check inside `wilson_ig.py` (its bytes are its `implementation_sha256`).

**D5 (R-804). The verifier: own provider table by basis; a third form.** `fresh_provider(basis)` constructs the
provider from the verifier's own table (M02 B15 independence), and it checks
`describe().provider_id`/`components` against the basis. In `revision_checks` the SYN-001 lines and the `pr-c1-v1`
lines stay textually as they are. A dispatch at the top sends the three new bases to a *declared-phase mixture-h*
form.
*Rejected:* running SYN-001's lines for every basis, which asks a non-SYN-001 provider for `lnK`/`h_<c>` and fails.

**D6 (R-805). The column is embedded with link rows.** The flowsheet face is the standalone declaration. Inlet pin
rows become link rows, product link rows are added, and every internal column is owned. `evaluate` runs the
standalone solve, which provides the EO start.
*Rejected:*
- *The column as an implicit black-box block* (outlets = f(inlets) via an inner solve and the implicit-function
  theorem). Its value depends on the warm start, so it is not a function of `x`, and `state_sha256` would no longer
  determine an evaluation (ADR 0008 D1).
- *Renaming internal columns to the flowsheet stream ids.* The column's attempt machinery (label rows, initializers,
  acceptance) reads inlet ids in many places; link rows touch none of them, and K03 eliminates them as aliases.

**D7 (R-806). S06 Q7: `F_ref = 1 mol/s` and a recovery definition row.** §4.7.4.
*Rejected:*
- *`F`/`F_c` frozen from the traversal.* That gives the wrong root when the feed moves (recycles), and the compiled
  constants would depend on a solve path.
- *Dimensionless slot rows* (`x − x*`). They need a new row kind, which `KIND_TOLERANCE` lacks.
- *Linear `n_c − x*·P`.* It is not `v − p`, so edge 3 could not continue on it (`homotopy.continuation_parameter`).

**D8 (R-807). The cascade is bound through the column.** A column with `top` and `bottom` inlets is S01's cascade
(S02 §1.2–1.3). A second wrapper over `solve_cascade` buys nothing.
*Rejected:* binding `syn001.cascade` separately.

**D9 (R-808). W27 registration version 3.** Adding provider rows to `registration_v2.json` changes a registered file
whose SHA-256 the v2 coverage records carry (W27v2-A21). Its R07(d) refuses two routes with one provider id. And with
no row at all, the S11 build's snapshot is refused (W27-R63), which would block the next release's W27 run.
*Rejected:* editing v2; not registering.

**D10 (R-809). `pr-lib-v1` stays library-only.** R-615 holds its exposure for Frank's ship decision and the clean-up
(F-4). A vapour-only, flash-less provider would admit routing models only.

**D11 (R-811). Wilson's real records are selectable in a source checkout and refused typed in a wheel.** The records
are repository-only until Frank's Q-F3 (R-706). R-615 rejected "expose in source checkouts only" for `pr-lib-v1`
because a wheel would carry a selectable basis without records. S11 distinguishes the case: Frank asked for the
binding on 2026-10-26, and the wheel's answer is an explicit `basis_unavailable` refusal, not a silent gap. This is a
default open to Frank (§7 Q1).

---

## 4. The design

### 4.1 The basis registry and what a revision writes

A data table in `models/revision_flowsheet.py`. It imports no provider class at module import (R-219).

| `component_set.record_source` | provider id | basis components | molar masses (kg/mol) | provider constructor (binder and verifier, each its own table) |
| --- | --- | --- | --- | --- |
| `benchmarks/m01/components.yaml` (`pr_c1.RECORDS_PATH`) | `pr-c1-v1` | `pr_c1.COMPONENTS` | the records (unchanged) | `PrC1Provider()` |
| `benchmarks/s05/components.yaml` (new) | `iapws95-v1` | `("H2O",)` | `iapws95.M` = 0.018015268 | `Iapws95Provider()` |
| `benchmarks/s10/records.yaml` (`wilson_ig.RECORDS_PATH`) | `wilson-ig-v1` | the records' ids, in file order | pinned constants equal to the file's `molecular_weight.value` (a test asserts equality) | `WilsonIdealGasProvider()` (the checkout's real records) |
| `benchmarks/s07/components.yaml` (new, generated) | `coolprop-heos-v1` | `(c,)`, where `c` is the revision's single declared component | the S07 table row's `M` | `CoolPropHeosProvider(c)` |
| any other value, absent included | `syn001` | `("A","B","C")` | `MOLECULAR_WEIGHTS` | `Syn001Provider()` |

**`component_basis(document)`** goes down the table top to bottom by string equality.
- For the CoolProp row, the declared `components` must be exactly one id that is admitted
  (`CoolPropHeosProvider.admitted()` ids). Otherwise it raises `RevisionError("unsupported",
  "components_unsupported", hint=…)`. The hint names the cause: `coolprop-heos-v1 serves exactly one admitted fluid
  per revision; got [<ids>]`, or the S07 exclusion reason for an excluded fluid.
- Its readers handle that raise:
  - `_read`, which turns it into `Unbound`, as today;
  - `validation.py:285`, which makes COMP-02 FAIL with the code and hint. No new check id is added, so every
    existing validation report is byte-identical;
  - `verify/certificate.py:665`, which raises `VerifierError("revision_unreadable(components_unsupported)")`.

**What a revision writes.**

| Basis | `record_source` | `components` |
| --- | --- | --- |
| SYN-001 | `benchmarks/syn001/components.yaml` (or, as today, anything unregistered) | a permutation of `A, B, C` |
| C1 | `benchmarks/m01/components.yaml` | a permutation of the five |
| IAPWS-95 | `benchmarks/s05/components.yaml` | `["H2O"]` |
| CoolProp | `benchmarks/s07/components.yaml` | `["<id>"]`, one S07 id (e.g. `["CO2"]`, `["H2O"]`) |
| Wilson | `benchmarks/s10/records.yaml` | a permutation of the three record ids (a binary is declared with the third component's flows exactly zero, ADR 0001 D3) |

**The two new record files** each validate against `schemas/component-record.schema.json`.

*Erratum 2026-10-27 (R-830):* T08.A32 admits both files as provider-identity record files, under their own clause
(vi). See `docs/reviews/S11-rulings.md` item 1.

- *`s05/components.yaml`* is written by hand. It holds one record, `H2O`:
  - name `water`; `identifiers {cas: "7732-18-5", formula: "H2O"}`;
  - `molecular_weight` 0.018015268 kg/mol, with provenance "IAPWS R6-95 (2018), M";
  - `elemental_composition {H: 2, O: 1}`, `VERIFIED`; `parameters {}`;
  - `rights` citing IAPWS, as S05 §16.3's attribution does;
  - `reference_convention: IAPWS95-ref-v1`.
- *`s07/components.yaml`* is generated by `docs/derivations/scripts/s11_coolprop_records.py` (it has `--check`) from
  `thermo/_coolprop_heos_fluids.FLUIDS`, one record per admitted row, in table order:
  - `id`, `name` and `identifiers.cas` from the row;
  - `molecular_weight` from `M`, with provenance "CoolProp 8.0.0, fluid <name> (MIT)";
  - `elemental_composition: null` with `elemental_verification: PENDING`. If the repository's record validator
    refuses `PENDING` with a null formula, use `NOT_APPLICABLE` and log it in `docs/S11A_DECISIONS.md`;
  - `parameters {}`;
  - `rights` citing CoolProp's MIT notice and the row's `bibtex_eos` (R-715's conditions);
  - `reference_convention: COOLPROP-DEF-ref-v1`.

  A test asserts that the file equals the generator's output and that each `M` equals the table's (float equality).

### 4.2 `ComponentBasis` and `SELECTABLE_BASES`

```
@dataclass(frozen=True)
class ComponentBasis:
    provider_id: str
    components: tuple[str, ...]
    molecular_weights: Mapping[str, float]
    record_source: str          # new, keyword-required; the registry key that selects it
```

- `SYN001_BASIS.record_source = "benchmarks/syn001/components.yaml"`, the path W27's `_syn001_line` already reads.
- `selectable_bases()` returns, in this fixed order: `SYN001_BASIS`, the C1 basis, the IAPWS-95 basis, the Wilson
  basis, then one CoolProp basis per row of `FLUIDS`. That makes 1 + 1 + 1 + 1 + 123 = **127** entries.
- `_SelectableBases` gains `__iter__` returning `iter(selectable_bases())`, so that one iteration builds the tuple
  once rather than N + 1 times.
- No entry reads a file except the C1 basis (its per-process records cache, unchanged). The Wilson molar masses are
  constants, so listing never needs the repository-only records.
- `benchmarks/l01/retake.py:93` constructs a `ComponentBasis` for `pr-lib-v1`. It passes
  `record_source=pr_lib.RECORDS_PATH`, and its output is unchanged (W27v2-A23).
- `MODEL_BASES` keeps its shape (model id → frozenset of provider ids). A CoolProp admission applies to every fluid.

### 4.3 Bind-time preconditions

The binder calls `provider_for(basis) -> PropertyProvider | Unbound` (new, in `revision_binding.py`) in place of
`basis_provider(basis)`. `basis_provider` stays the raising API that W27 calls.

| Basis | Precondition | Refusal (`Unbound`, kind `unsupported`) |
| --- | --- | --- |
| `coolprop-heos-v1` | `importlib.util.find_spec("CoolProp") is not None` | `basis_unavailable(coolprop-heos-v1)`, hint "the coolprop extra is not installed (pip install openflowsheet[coolprop])" |
| `wilson-ig-v1` | `wilson_ig.load_records()` succeeds | `basis_unavailable(wilson-ig-v1)`, hint naming `records_missing` and R-706/Q-F3 |
| `wilson-ig-v1` | `wilson_premises.violations(records) == ()` | `basis_premises_unmet(wilson-ig-v1)`, hint `"<P1|P2|P3>: <component> min <value> at T = <T, 4 s.f.> K"` for the first violation |

If the repository enumerates `Unbound` detail codes, both new codes are added there additively. The verifier's
`fresh_provider` runs the same two Wilson checks and raises `VerifierError` with the same codes.

**`thermo/wilson_premises.py` (new; pure; reads a `WilsonRecords`).** Let θ = T/1000 K, and take
`[θ_lo, θ_hi]` = the records' T domain / 1000. Let `(a, b, c, d)` be the vapour-pressure coefficients and `b0…b4`
the c_p^ig coefficients. For each component, the minimum of each function over the interval is taken over the two
endpoints and every real root in the interval of the stated cubic. The roots come from `numpy.roots`. A root counts
as real when |Im| ≤ 1e-12·max(1, |Re|), and each real root is refined by two Newton steps on the cubic.

| Premise | Function (S10C-spec §2.1) | Critical-point cubic | Holds iff the minimum is ≥ |
| --- | --- | --- | --- |
| P1 | `dlnPsat/dT = (−b/θ² + c/θ + 2dθ)/1000` (1/K) | `2dθ³ − cθ + 2b = 0` | 1e-9 1/K |
| P2 | `c_p^0L/R = (b0 − c) + b1θ + (b2 − 6d)θ² + b3θ³ + b4θ⁴` | `4b4θ³ + 3b3θ² + 2(b2 − 6d)θ + b1 = 0` | 1e-6 J/(mol K) after × R |
| P3 | `c_p^ig/R = b0 + b1θ + b2θ² + b3θ³ + b4θ⁴` | `4b4θ³ + 3b3θ² + 2b2θ + b1 = 0` | 1e-6 J/(mol K) after × R |

`R = 8.31446261815324`. The order of evaluation is components in file order, then P1, P2, P3; the first violation is
reported. The function also returns the minima, for gate G4.

### 4.4 The admission matrix and the typed refusals

| Model | `syn001` | `pr-c1-v1` | `iapws95-v1` | `coolprop-heos-v1` | `wilson-ig-v1` |
| --- | --- | --- | --- | --- | --- |
| `syn001.feed_source`, `syn001.product_sink`, `syn001.stream_splitter` | yes | — | **yes** | **yes** | **yes** |
| the other 10 `syn001.*` | yes | — | — | — | — |
| the 9 `c1.*` | — | yes | — | — | — |
| `syn001.column` (new) | **yes** | — | — | — | **yes** |
| `syn001.cascade` | not in `MODEL_BASES` (library-only) |

**Refusal reasons.** `_basis_refusal` keeps its hint text for every existing pair, and a test asserts the syn001↔c1
hints are byte-identical. For a pair involving a new basis, it appends a reason from a new table `_UNADMITTED`:
- a `syn001.*` thermal model on Wilson: "its EO face reads lnK and h_<c>; γ–φ faces are S11c";
- any thermal model on IAPWS-95 or CoolProp: "pure-fluid units are S11b (two-phase pure-fluid streams are not
  representable in nTP-v1)";
- `syn001.column` on C1: "pr-c1-v1 is vapour-only (S02 §0)";
- `syn001.column` on IAPWS-95 or CoolProp: "a pure fluid has no stage composition".

`syn001.cascade` is refused by the first branch, `model_unsupported(syn001.cascade)`, which gains the hint "bind
syn001.column with its top and bottom inlets connected (S02 §1: condenser none, reboiler none is S01's cascade)".

**What each basis lacks, and what that blocks.**

| Basis | Lacks | Blocks | S11 |
| --- | --- | --- | --- |
| `wilson-ig-v1` | `s` | isentropic units (pump, compressor, turbine), PS closures | refused; closing it needs a provider version 2 |
| `wilson-ig-v1` | `v`/`Z` | pump work (∫v dP; SYN-001's form gives 0), volumetric specifications | refused |
| `wilson-ig-v1` | `Psat`/`Tsat` property ids | nothing in S11 (the column uses `lnphi_<c>` and S10-C's band points) | — |
| `iapws95-v1`, `coolprop-heos-v1` | a PH flash; two-phase states under `nTP-v1` (the TP flash is degenerate in the saturation band) | valve or flash to quality, wet expansion, saturated mixtures; every thermal unit pending S11b's design | refused (S11b) |
| `pr-lib-v1` | liquid, flash, `s` | everything except routing | not selectable (D10) |

### 4.5 The routing models on every basis

`FeedSource`, `ProductSink` and `StreamSplitter` gain three optional construction fields, `property_provider`,
`reference_convention` and `domain` (`{"T": (lo, hi), "P": (lo, hi)}`). Their defaults are SYN-001's current
constants. `manifest()` reads them in place of the module constants. The three builders in `revision_binding.py`
pass `provider.describe()`'s values when `view.basis.provider_id != "syn001"`, and pass nothing otherwise. A test
asserts that the SYN-001 manifests are byte-identical (canonical-JSON SHA-256) to `8c34ecb0`'s. Nothing else in
these units changes: they evaluate no property.

### 4.6 The verifier

1. `fresh_provider(basis: ComponentBasis)` replaces `fresh_provider(provider_id)`. It has its own constructor table,
   with the same mapping as §4.1. It then requires `describe().provider_id == basis.provider_id` and
   `describe().components == basis.components`, or it raises `basis_mismatch(...)`. `FRESH_PROVIDERS` becomes the
   tuple of the five provider ids.
2. In `revision_checks`, a form is resolved at the top:
   `form = {"syn001": SYN, "pr-c1-v1": PR}.get(view.basis.provider_id, DECLARED_MIXTURE)`. The `SYN` and `PR`
   branches are today's code, untouched.
3. `DECLARED_MIXTURE` (new module `verify/forms.py`):
   - **Degeneracy and bands:** none, as for `PR` (`Degeneracy()`).
   - **Enthalpy flow of a flowing stream:** `Ḣ = n_tot · h(T, P, phase)`, from `evaluate_phase(properties=("h",))`,
     with `phase` the producer's declared `phase_capability` (`liquid` → LIQUID, `vapor` → VAPOR). If it is undeclared
     or `vapor_liquid`, the stream is `unlifted`, and every check reading it is a `blocked_check` (the existing
     mechanism). A dormant stream is 0.0 (ADR 0001 D3.1).
   - **Admissibility** of each stream whose enthalpy was read in a declared phase, as one check
     `phase_admissibility.stream.<S>`, category `phase_admissibility`:
     - γ–φ: `models.syn001.tp_state.single_phase_admissible`. It dispatches on the equilibrium form (S10-C), and the
       check carries A09's shared-implementation note;
     - pure fluid: LIQUID iff `T < T_c` and `P ≥ Psat(T)·(1 − 1e-9)`; VAPOR iff `T ≥ T_c` or
       `P ≤ Psat(T)·(1 + 1e-9)`. `Psat` is the provider's property id; `T_c` is read from the fluid's row of
       `thermo/_coolprop_heos_fluids.FLUIDS` (`"T_c"`; package data, not the binder) or from `iapws95.T_C`. If `Psat` is refused (`no_saturation`), the check is
       blocked with the provider's message.
4. **Negative control (G5):** a recording provider wrapper fails the test if `lnK` or any `h_<c>` key is requested
   from a non-SYN-001 provider anywhere in `verify_revision`.

### 4.7 `syn001.column` as a flowsheet unit

#### 4.7.1 The instance in a revision

`semantic_role: separator` (the schema enum has no `column`; nothing reads the role). Model id `syn001.column`. It is
a native model, so `version` is unread.

| Port | Direction | Multiplicity | Declared `phase_capability` on its connection | Meaning |
| --- | --- | --- | --- | --- |
| `feed` | in | many (0…N−2) | required: `liquid` or `vapor` | side feeds. A stream's stage is the parameter `feed_stage.<connection id>`. Feeds are named `feed1, feed2, …` in connection order (the `SideFeed.port` names in row ids) |
| `top` | in | 0 or 1 | required: `liquid` or `vapor` | if connected: condenser `none` |
| `bottom` | in | 0 or 1 | required: `liquid` or `vapor` | if connected: reboiler `none` |
| `distillate` | out | 1 | `vapor` or `liquid` | without `top`: `vapor` means a partial condenser, `liquid` a total condenser. With `top`: must be `vapor` (it is v₁) |
| `bottoms` | out | 1 | `liquid`, or undeclared | l_N |

A configuration contradiction is refused `specification_conflict(<U>.<port>)`. A missing declaration is refused
`port_unsupported(<U>.<port>)`, with a hint that says what to declare. If the binder requires every multiplicity-1
port to be wired, `top` and `bottom` are declared multiplicity `many`, and the unit enforces "at most one" (a fact
WO-B2 checks). The unit reads its optional and possibly empty ports through `wiring.streams.get(port, ())`,
because `Wiring.many` refuses an empty port.

**Instance parameters** (Quantities):
- `stage_count` (dimensionless, integer-valued);
- `stage_pressure.<j>` (Pa) for every `j = 1..N`, all required. This is S02 §1.5's profile, exactly as written, with
  no formula, so every registered standalone case is reproducible;
- `feed_stage.<connection id>` (dimensionless, integer-valued) for every `feed` connection, and for nothing else;
- `stage_duty.<j>` (W), optional, only at a stage whose slot is not an end specification. Absent means 0.0.

**End specifications** are revision specifications (pins), read through two `SpecificationChoice`s. `condenser` is
present iff the condenser is not `none`; `reboiler` is present iff the reboiler is not `none`. Each option's target
is the instance `{instance}`:

| End | Options (path → `EndSpecification`) | Kind / SI unit |
| --- | --- | --- |
| condenser | `condenser.reflux_ratio`, `condenser.distillate_rate`, `condenser.duty`, `condenser.purity.{component}`, `condenser.recovery.{component}`, `condenser.temperature.{key}` (key = stage) | dimensionless; molar_flow; heat_rate; dimensionless; dimensionless; temperature |
| reboiler | `reboiler.boilup_ratio`, `reboiler.bottoms_rate`, `reboiler.duty`, `reboiler.purity.{component}`, `reboiler.recovery.{component}`, `reboiler.temperature.{key}` | as above |

The pin encodings follow the existing `PinColumn` and `pin_encodings` pattern, so `test_t07_r6_hints` covers them.

#### 4.7.2 Structure, and what is checked when

`column_unit.py` (new) defines `ColumnStructure`. It holds the unit id; N; the condenser and reboiler kinds; the
pressures; the duties; the end specifications; and the placed inlets as `(port, stage, declared phase, stream id)`.
It also defines a pure parser `column_structure(instance: InstanceView, components) -> ColumnStructure`, which the
builder and the verifier share. `structural_spec(structure) -> ColumnSpec` builds a `ColumnSpec` whose inlet states
carry the declared phase and `n = (nan,)*C, T = nan, P = nan`. It may be passed only to:
- `declared_rows(..., links=...)`;
- `column_solve.lifted_splits`;
- the column's zero-flow forms, closure types and split temperatures.

A test runs each of these on a structural spec and asserts that no NaN reaches any output: every parameter is
finite, and every id is free of `nan`.

**At bind** (the builder, as a `SpecificationError` or `RevisionError`), the *structural* subset of S02 §5 S1–S10
and S06 §5 I1–I6 is checked: stage count, kinds, pressure monotonicity, feed placement (one per stage, not at a
slot stage), the presence and kind of each end specification, and its component and stage. S10-C D8's refusal of
`purity`, `recovery` and `temperature` on γ–φ is checked here too, as
`specification_unsupported(<U>.<end>.<kind>)`, with the S10-C admitted kinds in the hint.

WO-B1 first writes the split of every S/I item into "structural" and "inlet-dependent" in `docs/S11B_DECISIONS.md`.
It may factor predicates out of `column.validate` only without changing `validate`'s order or messages, which the
S08 and S10-C identity gates prove.

**At evaluate,** the full standalone `validate` runs on the real inlet states, inlet-dependent items included
(domain, dormancy, I3, I4, I6, R7). Its refusal becomes the unit's typed failure.

#### 4.7.3 The flowsheet face: `contribute`

`declared_rows(spec, provider, context, *, links: FlowsheetLinks | None = None)`. With `links=None`, nothing changes.
With links:

1. **Inlet link rows** replace the pin rows. They keep the same row ids, `inlet_row_id(U, port, "n", c)`, `"T"`,
   `"P"`, and their kinds. The value is `r = v_stream − v_internal`, where `v_internal` is
   `flow_id(inlet_stream(U, port), c)` (or T, P) and `v_stream` is the connected flowsheet stream's column. The
   family is `COL-inlet-link`. The internal inlet columns stay owned.
2. **Product link rows** are added:
   `<U>:product:distillate:n:<c>`, `<U>:product:distillate:T`, `<U>:product:distillate:P`, and the same for
   `bottoms`. Each value is `v_stream − v_internal`, with these internal columns:
   - distillate: `vapor_id(U,1,c)` (condenser none or partial) or `distillate_id(U,c)` (total), and
     `stage_temperature_id(U,1)`, `stage_pressure_id(U,1)`;
   - bottoms: `liquid_id(U,N,c)`, `stage_temperature_id(U,N)`, `stage_pressure_id(U,N)`.

   The kinds are molar_flow, temperature and pressure; the family is `COL-product-link`; the accumulation is that of
   `definition_row`.
3. **Inverse slots** follow §4.7.4.
4. **Variables:** the standalone `variable_ids` (all owned, internal inlet columns included), plus one `recovery_flow`
   column per recovery slot. The flowsheet stream columns are not owned.
5. **Manifest:** built per instance. `property_provider`, `reference_convention` and `domain` come from the
   provider's `describe()`. The equations are `COLUMN_EQUATIONS + INVERSE_EQUATIONS + FLOWSHEET_EQUATIONS` (new: the
   two link families and the recovery definition). The limitations are §4.11's L-COL rows. The registry's manifest for
   `syn001.column` is the one built on SYN-001.

The slot rows must be the rows the binder records as the instance's specification rows for its two end pins, as for
every other unit's pinned specification. Then edge 3's `continuation_parameter` qualifies them (S11.A24). If the
binder's promotion naming differs from the column's `"<column>*"` parameters, the flowsheet face uses the binder's
names (WO-B3 checks this).

#### 4.7.4 S06 §15 Q7: `F`, `F_c`, `ν*`, `π*` in a flowsheet (ruling)

Standalone (unchanged): `F_c = Σ_k n_{k,c}` and `F = Σ_c F_c` over the pinned inlets; `ν* = fl(r*·F_c)`;
`π* = fl(x*·F)`. In a flowsheet the inlet flows are solved variables, so a parameter formed from them is not a
constant of the document. The ruling:

| Slot | Flowsheet rows | Pinned parameters | New column | Kinds |
| --- | --- | --- | --- | --- |
| `purity` (x* of c at end e, product total P) | S06's rows and ids exactly: definition `F_ref·n_c − u·P`, slot `u − π*` | `purity_reference* = F_ref = 1.0` (mol/s); `π* = fl(x*·1.0) = x*` | none (`purity_flow` u as S06) | molar_flow_squared; molar_flow |
| `recovery` (r* of c at end e) | definition `<U>:stage:<j>:spec:recovery_definition`: `F_ref·n_c − w·Σ_k n_{k,c}`; slot `<U>:stage:<j>:spec:recovery`: `w − ν*` | `recovery_reference* = F_ref = 1.0` (mol/s); `ν* = fl(r*·1.0) = r*` | `<U>.stage.<j>.recovery_flow` (w, molar_flow) | molar_flow_squared; molar_flow |
| `temperature` | unchanged: `T_s − T*` | `T*` | none | temperature |

- In the recovery row, `Σ_k n_{k,c}` runs over the column's internal inlet columns in `spec.inlets()` order (S06 §1's
  order), and the sum is left-associated.
- `n_c` is the product's flow at that end.
- At a root, `u = F_ref·x*` gives `n_c = x*·P`, and `w = F_ref·r*` gives `n_c = r*·F_c`: **the standalone roots, for
  any `F_ref > 0`**.
- `F_ref = 1 mol/s` makes `π* = x*` and `ν* = r*` exactly, so the continuation parameter is the user's number.
- The rows are regular where the standalone ones are: `∂/∂u = −P ≠ 0` at a flowing product; `∂/∂w = −F_c`, which is
  non-zero where I3 holds. I3 is checked at evaluate, and the verifier checks `F_c > 0` at `x_final`.

Tolerance meaning, recorded as limitation L-COL-6: a purity slot's tolerance acts on `x` directly (`|x − x*|` ≤ the
molar_flow tolerance ÷ 1 mol/s). The standalone tolerance acts on `F·x`.

#### 4.7.5 `evaluate`, the EO start and the stage splits

- `evaluate(inlets, context)`:
  1. Build the full `ColumnSpec` from the structure and the inlet `StreamState`s, keyed by port in wiring order.
  2. Each inlet must be in its declared phase by `tp_state.single_phase_admissible`, which dispatches on the form.
     Otherwise return the typed failure `inadmissible_phase(<port>, <PHASE>)`, as the pump does.
  3. Call `solve_column(spec, provider)` under its own registered policy (`S02_TARGET_POLICY`, the standalone path,
     S08 Stage B included).
     - A `CascadeFailure` becomes a failed `UnitEvaluation` carrying its cause.
     - A `DormantAnswer` becomes zero-flow outlets.
     - `AcceptanceDefectError` propagates: it is a defect, not a user error.
  4. On success, return:
     - `outlets` = `{distillate: (product flows, T₁, P₁), bottoms: (l_N, T_N, P_N)}`;
     - `duty = None` (the duties are owned stage columns);
     - `phase_signature = None` (the stage regimes reach the region through the staged splits and the owned
       columns);
     - `owned` = every owned column of the flowsheet face. Where its id is a standalone column, the value comes from
       the solution. The flowsheet-only values are `u = fl(n_c/P)` for purity and `w = fl(n_c/F_c)` for recovery,
       since `F_ref = 1`.
- **`UnitEvaluation.owned: Mapping[str, float] = {}`** (new). It must be empty on any status other than `ok`
  (`__post_init__`). `_start_from_pass` copies each `owned` entry whose name is wanted, after duty, work and extent.
  For every existing unit `owned` is empty, so every start is unchanged. If a consumer requires a non-`None`
  `phase_signature` from a unit that has owned label columns, the engineer escalates and does not invent one.
- **Staged splits.** The region solver must see, for each column, the per-stage `LiftedSplit`s, zero-flow forms,
  closure types and split temperatures that `column_solve` gives the standalone solve:
  - `orchestrator/splits.lifted_splits(instances, components, *, staged=None)` inserts
    `staged[unit_id]` (a tuple) at that instance's declaration position. `staged=None` leaves the output identical;
  - `executor._splits`, `_closure_types`, `_zero_flow_forms` and `_split_temperatures` merge the column's entries.
    The column computes them from `structural_spec` and the existing helpers;
  - a stage pseudo-unit belongs to the region that holds its equilibrium rows;
  - `check_agreement` accepts staged splits.
- **Policy.** The column needs `T05b-phase-contract-v2` (its policy is `s01-default-v1`). A revision solve whose
  policy carries v1 and whose binding holds a column ends `CAPABILITY_UNAVAILABLE`, with cause
  `phase_contract_unsupported(syn001.column)`, before the traversal. The registered column flowsheet cases solve
  under `s01-default-v1`, if the application's policy registry accepts it for a revision. Otherwise WO-B3 registers
  `s11-column-v1` = `S01_DEFAULT_V1` with a new id, in one isolated commit, and logs it.

### 4.8 The column's verifier checks (`verify/column.py`)

The rules are typed against a local `Protocol` for the table's `Unit`, so the module imports no `verify.table` at
run time. `MODEL_CHECKS["syn001.column"]` registers them.

| Category | Check id | Value (tolerance kind) |
| --- | --- | --- |
| material_balance | `material_balance.<U>.<c>` | `Σ_inlets n_c − n_c(distillate) − n_c(bottoms)` (molar_flow) |
| energy_balance | `energy_balance.<U>` | `Σ_inlets Ḣ + Q₁ + Q_N + Σ_j Q_j* − Ḣ(distillate) − Ḣ(bottoms)` (heat_rate). The Ḣ are the table's stream enthalpies; Q₁ and Q_N are `stage_duty_id` at `x_final` when they are ends |
| specification | `specification.<U>.<end>` | the achieved quantity minus its target: reflux `r/d`; boil-up `v_N/l_N`; rates; duty; purity `n_c/P`; recovery `n_c/Σ_k n_{k,c}(x_final)`, with `F_c > 0` required or the check fails; temperature `T_s` |
| phase_admissibility | `phase_admissibility.<U>.<port>[.<S>]` | the declared ports (all five), by the existing machinery |
| phase_admissibility | `phase_admissibility.<U>.stage.<j>` | `column_solve.acceptance_failures(spec, fresh, declared, x_final, regimes)` restricted to stage j's items; 0 if none fail. It carries A09's shared-implementation note |
| phase_admissibility | `phase_stability.<U>.stage.<j>` (γ–φ only) | `WilsonIdealGasProvider.stability(liquid_j, "LIQUID", context)` reports no split (Q-F4) |

The verifier passes the column's staged splits to `lifted_splits` (`certificate.py`, one call site). Every consumer
that maps `split.unit` to an instance resolves a stage pseudo-unit to its column by the prefix
`stage_unit(U, j)`. WO-B4 inventories those consumers (`grep -n "split.unit\|instances\["` over `verify/`) in
`docs/S11B_DECISIONS.md`.

### 4.9 The cascade

See D8 and §4.4. No code.

### 4.10 W27 registration version 3 (`docs/derivations/W27-registration-v3.md`, transcribed from this section)

- **W27v3-R01.** The version switch accepts `3`. Versions 1 and 2 behave byte-identically. The next release's
  preflight and release gate select `3`.
- **W27v3-R02.** `provider_methods` is v2's table plus `iapws95-v1 → iapws95`,
  `wilson-ig-v1 → activity_coefficient` and `coolprop-heos-v1 → pure_helmholtz`.
- **W27v3-R03.** `methods` gains `pure_helmholtz`: "a pure-fluid multiparameter Helmholtz EOS other than IAPWS-95
  (CoolProp HEOS); matches no case method".
- **W27v3-R04.** `model_functions` gains `syn001.column: {function: null, offers: [], why_none:
  "column_function_unregistered"}`. Registering a `column` function against the archive is a workstation follow-on.
- **W27v3-R05.** `PROVIDER_LINES_V3(basis, ids, every)`:
  - `pr-c1-v1` and `pr-lib-v1` keep their v2 lines;
  - every other basis takes `ROOT / basis.record_source`, reading `{id, name, formula, cas, synthetic}` from each
    record's `identifiers`, with `phases = every` (from `describe().phases`) for each component;
  - a provider with no line is refused.
- **W27v3-R06.** R07(d) is replaced: two routes with the same key `(provider_id, record_source, components)` are
  refused.
- **W27v3-R07.** R05's tie-break is the route key in code-point order: `provider_id`, then `record_source`, then the
  components joined by `,`.
- **W27v3-R08.** Snapshot S4 is the S11 build's routes (127), generated at WO-I1 and registered with its SHA-256.
- **Effects:** the Wilson records carry no CAS RN (R-706), so its route serves no case; CoolProp's method matches no
  case; IAPWS-95's route serves the property side of IDAES `iapws95` cases.
- *Erratum 2026-10-27 (R-832):* the Wilson route serves no case because of the new rule **W27v3-R09** (the spelling
  rule skips a record with no CAS RN); without it the snapshot is refused. W27v3-A08 is restated and A09 is added
  (`docs/reviews/S11-rulings.md` item 3; carried by I1b).

Data goes in `registration_v3.json`, from `docs/derivations/scripts/w27_registration_v3.py --check`.

### 4.11 The envelope, T08, `LIBRARY_ONLY_PROVIDERS` and the harvest

- `property_model.providers: [coolprop-heos-v1, iapws95-v1, pr-c1-v1, syn001, wilson-ig-v1]`.
  `other_basis_providers` gains the three new ids, each with a limitation row:
  - **L-S11-1 (IAPWS-95):** H2O; 273.16–1273.15 K, 10²–10⁸ Pa; routing models only; S05's validation.
  - **L-S11-2 (CoolProp):** one fluid per revision, 123 fluids, S07's tiers and domains; routing only; needs the
    extra.
  - **L-S11-3 (Wilson):** the three record components; 300–400 K, 30–200 kPa; routing and column; records repository
    only (wheel: `basis_unavailable`); P1–P3 at bind; S10 VAL-1–3 bands (the VAL-3 latent-heat miss is carried);
    cross-architecture by tolerance.
- **U02** becomes "Any property method other than the five selectable bases". Its outcome names `pr-lib-v1` as
  library-only (R-569), and its three tests stay.
- **U04** becomes "`syn001.cascade` as a model id (bind `syn001.column` with `top`/`bottom`)". The column's former
  U04 evidence moves to a binding test.
- `unit_models.members` gains `syn001.column` (23), and its statement is updated.
- **L-COL-1…8:**
  1. Feeds are single-phase and declared, one per stage, not at a slot stage (S01 DECISION 8, S02 §1.4).
  2. No side draws, pump-arounds, efficiencies or hydraulics (S02 §14).
  3. A total condenser gives saturated liquid; there is no total reboiler.
  4. On Wilson, only ratio, rate and duty specifications (S10-C D8).
  5. No uniqueness, multiplicity or feasibility claim beyond S06 §14.
  6. The `F_ref` tolerance meaning (§4.7.4).
  7. Stage B on Wilson is tested at the opening level only (S10-C).
  8. SYN-001 columns are synthetic: no validation.
- `LIBRARY_ONLY_PROVIDERS == {"pr-lib-v1": "S04"}`.
- No earlier harvest entry is edited. S11's manifest is harvested by appending, which moves `HARVEST_SIZE` by S11's
  appended counts only. `docs/support-matrix.md` is re-emitted.

### 4.12 Performance

- `selectable_bases()`: ≤ 50 ms per call (127 small objects; no file read beyond C1's cache).
- Bind of a Wilson revision: one record parse and the P1–P3 check (< 5 ms).
- A column flowsheet's traversal costs one standalone column solve per pass (two passes with tears). The global EO
  solve starts at the standalone root, so it needs ≤ 3 Newton iterations when there is no recycle (G6).
- Memory and traffic: the declaration grows by `14N + O(C·N)` columns per column, with the sparsity of the
  standalone declaration plus `2(C + 2)` link rows per product and `(C + 2)` per inlet. K03 eliminates the link rows
  as aliases.
- Gate: wall time ≤ 3× the standalone solve of the same case + 2 s. Record the numbers; if the gate is exceeded,
  escalate before optimising.

### 4.13 Disposition of every deferred entry (digest §6)

| # | Entry | S11 |
| --- | --- | --- |
| 1, 2, 17 | R-535; `S02_DECISIONS.md:17`; D1-rulings:58 | **done**: the column is bound; L-COL rows; the cascade is covered through the column (U04 hint) |
| 3 | S06 §15 Q7 | **done**: §4.7.4, R-806 |
| 4, 15 | S07 §3.4, §12.4; S07 brief:22 | **done**: key, admission (routing), W27 v3, rows, envelope. Thermal units **left** (S11b) |
| 5, 6, 14 | S05 §16.4 and Q-8; A25, F-3; R-616 | **done**: selectable, W27 `iapws95`, rows; A25 **superseded** (R-810) |
| 7 | ADR 0045, ADR 0046 D9 (library-only) | **superseded** by ADR 0050 D3 |
| 8, 11 | Q-F2; R-709 | **superseded** by Frank, 2026-10-26 (R-810) |
| 9 | S10 A27, :976 | **superseded** / decided; :1035, :1055 (NRTL/LLE) **left**: an interface ADR first |
| 10 | S10C design :66, :526, :566 Q1 and Q3 | **superseded** (R-810): the column and routing on Wilson |
| 12, 16 | R-781 and S10-C review F2; V02_STATE:115 | **done**: P1–P3 at bind (§4.3) |
| 13 | R-568, R-569 | **applied**: axis rows, L-rows, U02 text; harvest untouched |
| 18 | R-615 (`pr-lib-v1`) | **left**: Frank's ship decision and the clean-up (R-809) |
| 19 | T08 A20 | **holds**: providers axis = `SELECTABLE_BASES`' providers |

---

## 5. Work orders

**Branches:**
- WO-0 runs on `wp/S11`.
- Track A runs on `wp/S11-a` and track B on `wp/S11-b`, each branched from `wp/S11` after WO-0, in worktrees under
  `.claude/worktrees/`.
- I1 and I2 run on `wp/S11`.

**Commits and logs:**
- Each WO is committed by itself, with messages naming S11 and the WO.
- Each per-commit check runs the tests the commit touches, plus `scripts/s11_identity.py` whenever the commit
  touches `revision_binding.py`, `revision_flowsheet.py`, `column.py`, `models/__init__.py`, `orchestrator/`,
  `verify/` or the routing units (in the background, one wait).
- There is no intermediate full gate.
- Decisions are logged one per line in `docs/S11A_DECISIONS.md` and `docs/S11B_DECISIONS.md`, as
  `DECISION: <q> → <choice>. Alternative: <x>. Reversible by: <how>.`

**File ownership.** The tracks touch disjoint files, with one exception in time: B4 starts only after A3 is merged
into `wp/S11`, and B rebases on it first. Only B4 then touches `verify/table.py`, `verify/certificate.py` (its
`lifted_splits` call) and `verify/zero_flow.py`.

| WO | Owner | Files | Depends on | Acceptance |
| --- | --- | --- | --- | --- |
| **WO-0** identity gate | Opus | `scripts/s11_identity.py` (new), `tests/test_s11_identity_gate.py` (new), the two decisions-log stubs | — | On an unmodified tree: `S11-IDENTITY PASS n=<N> changed=[]`. Control: a scratch copy whose `_basis_refusal` hint differs by one character gives FAIL naming the key (recorded in S11A_DECISIONS) |
| **A1** registry and selection | Opus | `models/revision_flowsheet.py`, `application/revision_binding.py` (`provider_for`, `basis_provider`, `_SelectableBases.__iter__`), `application/validation.py` (COMP-02 path), `thermo/wilson_premises.py` (new), `benchmarks/s05/components.yaml`, `benchmarks/s07/components.yaml`, `docs/derivations/scripts/s11_coolprop_records.py`, `benchmarks/l01/retake.py`, `tests/test_s11_bases.py` (new), `tests/test_m02_join.py` | WO-0 | S11.A01–A10; identity PASS |
| **A2** routing on every basis | Opus | `models/syn001/feed.py`, `sink.py`, `splitter.py`, `application/revision_binding.py` (three builders, `MODEL_BASES` rows, `_UNADMITTED`, cascade hint), `tests/test_s11_routing.py` (new) | A1 | S11.A11–A15; identity PASS |
| **A3** verifier forms | Opus | `verify/certificate.py` (`fresh_provider` and its call), `verify/table.py` (form dispatch, top of `revision_checks`), `verify/forms.py` (new), `tests/test_s11_verifier_forms.py` (new) | A2 | S11.A16–A19; identity PASS (SYN and C1 certificates unchanged) |
| **A4** W27 v3 | Opus | `docs/derivations/W27-registration-v3.md`, `docs/derivations/scripts/w27_registration_v3.py`, `benchmarks/m06/openidaes450/registration_v3.json`, `benchmarks/m06/w27/{coverage,registration,snapshot}.py`, `tests/test_s11_w27_v3.py` (new) | A1 | S11.A30–A33; all existing W27 tests pass unchanged (*erratum 2026-10-27, R-837: restated as read through `v2_binder()`, `docs/reviews/S11-rulings.md` item 8*) |
| **A5** envelope (providers) | Sonnet | `benchmarks/t08/support_envelope.yaml` (providers, U02, L-S11-1…3), `docs/support-matrix.md`, `tests/test_t08_w2_support_envelope.py` (providers, `LIBRARY_ONLY_PROVIDERS`), `tests/test_s05_envelope.py`, `tests/test_s07_registration.py`, `tests/test_s10_provider.py` | A2 | `t08_support_matrix.py --check` OK; S11.A34 |
| **B1** flowsheet face | Opus | `models/syn001/column.py` (`links`), `models/syn001/column_unit.py` (new: `ColumnStructure`, `column_structure`, `structural_spec`), `tests/test_s11_column_face.py` (new) | WO-0 | S11.A20–A23; the S08 and S10-C lines reproduce |
| **B2** unit and binding | Opus | `column_unit.py` (`ColumnUnit`), `application/column_binding.py` (new: `_COLUMN` signature, builder), `models/__init__.py` (`owned`), `orchestrator/revision.py` (`_start_from_pass`), `tests/test_s11_column_unit.py` (new; registers the builder in a monkeypatched `MODEL_BUILDERS`, as `test_m02_wo8_region` does) | B1 | S11.A25–A27; identity PASS |
| **B3** orchestration and cases | Opus | `orchestrator/splits.py`, `orchestrator/executor.py`, the policy check, `benchmarks/s11/flowsheets/*.json` (new), `tests/test_s11_column_solve.py` (new) | B2 | S11.A24, A28, A29 (G6); timings recorded |
| **B4** column verifier | Opus | `verify/column.py` (new), `verify/certificate.py` (the `lifted_splits` call), `verify/table.py` (stage pseudo-units in consumers), `verify/zero_flow.py`, `tests/test_s11_column_verifier.py` (new) | B3 and A3 merged | S11.A35–A38 |
| **I1** registration | Opus | `application/revision_binding.py` (the column in `MODEL_BUILDERS`/`MODEL_SIGNATURES`, `MODEL_BASES = {syn001, wilson-ig-v1}`), `verify/table.py` (`MODEL_CHECKS` entry), the envelope (members, U04, L-COL), count and sample tests (§8.3), W27 S4 | A and B merged | S11.A39–A41; `t08 --check`; W27 v3 S4 registered |
| **I2** gates and records | Opus | `evidence/S11/<commit>/manifest.json`, harvest append, `HARVEST_SIZE`, ADR 0050 status line, `docs/progress.md` | I1 | G1–G8 numbers in the manifest; full `scripts/gate.sh` PASS; CI green on both architectures; then **one** `reviewer` pass |

Agents: at most two at a time (track A and track B), each WO ≤ 150k context. An engineer that reaches the cap
commits, writes where it stopped in its decisions log, and ends.

---

## 6. Assertions and verification gates

Base for every identity comparison: `8c34ecb0`. Tolerances are the registered ones unless stated.

### 6.1 Assertions

**Bases (A1, A2).**
- **S11.A01** `len(SELECTABLE_BASES) == 127`. The order is SYN-001, C1, IAPWS-95, Wilson, then CoolProp in `FLUIDS`
  order. `tuple(SELECTABLE_BASES)` equals `selectable_bases()`.
- **S11.A02** For every entry `b`, `basis_provider(b).describe()` gives `(provider_id, components) == (b.provider_id,
  b.components)` (Wilson and CoolProp skipped with a reason when unavailable).
- **S11.A03** `component_basis` returns the expected basis for each registered `record_source`, and for each of the
  123 CoolProp ids. An unregistered value (three probes, absent included) returns `SYN001_BASIS`.
- **S11.A04** CoolProp: two components, an unknown id, and each of the 13 excluded names are each
  `components_unsupported`, with the stated hint.
- **S11.A05** Molar masses: IAPWS-95 is `0.018015268`; each CoolProp `M` equals the table's; Wilson's equal the
  file's. Float equality in each case.
- **S11.A06** `s11_coolprop_records.py --check` is OK, and both record files validate against
  `component-record.schema.json`.
- **S11.A07** `wilson_premises` passes on the real records and on the verification records. For every component,
  each minimum rounded to 3 significant figures equals the `positivity` entry of
  `benchmarks/s10c/reference_values.yaml`: `dlnpsat_dT` (P1), `cp_liquid` (P2) and `cp_ig` (P3). For example, the
  real records give CH3OH 0.027 / 69.7 / 44.2 and H2O's c_p^0L 63.0 (S10C-spec §2.1). Any mismatch fails, and so
  does a minimum taken at a point that is neither an endpoint nor a real root of the stated cubic.
- **S11.A08** Mutation: the real records with T domain `[300, 800]` K give `basis_premises_unmet(wilson-ig-v1)`.
  The hint names P2 and H2O, with T in [750, 800] K.
- **S11.A09** With `find_spec("CoolProp")` patched to `None`, a CoolProp revision gives `basis_unavailable`. With the
  Wilson records path absent, a Wilson revision gives `basis_unavailable`.
- **S11.A10** A CoolProp revision with two components fails validation through COMP-02 with the code. A SYN-001
  revision's validation report is byte-identical to the base.
- **S11.A11** The three routing models' SYN-001 manifests are byte-identical to the base (canonical SHA-256).
- **S11.A12** On each of IAPWS-95 (H2O liquid at 300 K, 1 MPa), CoolProp (CO2 vapour at 300 K, 1 bar) and Wilson
  (liquid at 330 K, 101 325 Pa), `feed → splitter(0.3) → 2 sinks` binds and solves `CONVERGED`. The material balance
  is exact (`==`). The outlet T and P equal the feed's.
  *Erratum 2026-10-27 (R-835):* restated as "within 2 ulp per component", with a registered non-exact Wilson case
  (0.4, 0.4, 0.8). See `docs/reviews/S11-rulings.md` item 6.
- **S11.A13** Every refused pair of §4.4 gives `model_unsupported(<id>)`, with its reason. The syn001↔c1 hints are
  byte-identical to the base.
  *Erratum 2026-10-27 (R-841):* the hint names every basis the model binds on. Byte-identity holds only for models
  whose `MODEL_BASES` S11 leaves unchanged. See `docs/reviews/S11-rulings.md` item 12.
- **S11.A14** `syn001.cascade` is refused, with the hint.
- **S11.A15** `pr-lib-v1` records select SYN-001 and are refused `components_unsupported` (R-569 unchanged).

**Verifier (A3).**
- **S11.A16** A12's three flowsheets with declared phases verify: every check is computed, and the splitter energy
  satisfies |value| ≤ energy tolerance.
- **S11.A17** The same flowsheets without declared phases: the energy checks are blocked with the unlifted note, and
  none passes silently.
  *Erratum 2026-10-27 (R-841):* restated. The binder refuses a `vapor_liquid` routing port (asserted), so the unlifted
  path is exercised on `revision_checks`. See `docs/reviews/S11-rulings.md` item 12.
- **S11.A18** The recording provider sees no `lnK` and no `h_<c>` requested from a non-SYN-001 provider.
- **S11.A19** `fresh_provider` with a basis whose components disagree raises `basis_mismatch`.

**Column (B1–B4).**
- **S11.A20** In link mode, the declaration's DOF equals the standalone's. The link rows replace exactly the
  `(C + 2)·n_in` pin rows and add `2(C + 2)` product rows (plus one row and one column per recovery slot).
- **S11.A21** `links=None` gives a `ProblemSpec` identical (ids, parameters `float.hex`, kinds) to the base for
  S02 M1–M4, P1 and S06 J1–J8.
- **S11.A22** NaN guard: on a structural spec, every output of the five permitted functions is NaN-free.
- **S11.A23** The S08 and S10-C identity lines reproduce exactly.
- **S11.A24** For a column region, `continuation_parameter` qualifies the column's slot rows.
- **S11.A25** `UnitEvaluation(status != ok, owned={...})` raises. `_start_from_pass` is unchanged for every existing
  unit (identity family C).
- **S11.A26** The structural refusals at bind: one test per structural S/I item, in B1's inventory.
- **S11.A27** The Wilson column with a `purity` end gives `specification_unsupported(<U>.condenser.purity)`.
- **S11.A28** Feed and phase contract: a revision with a column under a v1 policy gives `CAPABILITY_UNAVAILABLE
  phase_contract_unsupported(syn001.column)`.
- **S11.A29 (G6)** `feed_source(s) → column → 2 product_sinks`, with the feed pinned to each registered standalone
  case's inlets, reproduces the registered standalone values. This covers S02 M1–M4; S06 J1–J8 (inverse, through
  §4.7.4); S10 C-MW and C-EW (Wilson). Every product flow, T, P, Q₁ and Q_N is within that case's registered state
  tolerance, measured as max |Δ|/tol ≤ 1. The global EO solve takes ≤ 3 Newton iterations from the traversal start.
  One SYN-001 recycle case (bottoms split 0.2 back to a side feed) converges and verifies.

**W27 (A4).**
- **S11.A30** The W27 v1 and v2 outputs on every registered state are byte-identical.
- **S11.A31** v3 refuses a duplicate route key, and admits 123 CoolProp routes with distinct keys.
- **S11.A32** `w27_registration_v3.py --check` is OK.
- **S11.A33** An IAPWS-95 route row reads CAS `7732-18-5` from `benchmarks/s05/components.yaml`.

**Envelope (A5).**
- **S11.A34** The providers axis is the five ids; `LIBRARY_ONLY_PROVIDERS == {"pr-lib-v1": "S04"}`.

**Column verifier (B4).**
- **S11.A35** The A29 cases' certificates verify: material ≤ the molar_flow tolerance, energy ≤ the energy tolerance,
  specifications within tolerance, and every stage item passes.
  *Erratum 2026-10-27 (R-831):* on Wilson, the derivative witness differences absent-component zero columns with a
  forward five-point stencil, so C-MW, C-EW and the stripper can verify. R-281 is unchanged. See `docs/reviews/S11-rulings.md` item 2.
- **S11.A36** Mutation: `Q₁ += 10 ×` energy tolerance in `x_final` makes `energy_balance.<U>` FAIL. Swapping one
  stage's `T` with its neighbour's makes the residual and stage checks FAIL.
- **S11.A37** For C-MW and C-EW, `phase_stability.<U>.stage.<j>` passes at every stage.
- **S11.A38** A recovery check with `F_c = 0` at `x_final` (constructed) FAILs.

**Integration (I1).**
- **S11.A39** `set(MODEL_BASES) == set(MODEL_BUILDERS) == set(MODEL_SIGNATURES)` has 23 members, and
  `MODEL_BASES["syn001.column"] == {"syn001", "wilson-ig-v1"}`.
- **S11.A40** The W27 v3 snapshot of the S11 build equals S4: 127 routes, with no `SnapshotUnsupportedError`.
- **S11.A41** The served MCP tool-list digest is unchanged.

### 6.2 Gates

| Gate | Criterion |
| --- | --- |
| **G1 identity** | `scripts/s11_identity.py` prints `S11-IDENTITY PASS n=<N> changed=[]`. Family A: S08's 52 configurations and S01 C1–C5, with S08's fields. Family B: every `ph_state` call in the T05/T05b tests (S10-C's family). Family C: every `bind_revision_flowsheet` call of the whole suite, keyed by test node id and call index. Its digest covers the document's SHA-256, the outcome kind, code and hint, and for a binding the `ProblemSpec` ids, kinds and parameters (`float.hex`). Keys present in both trees must be equal, except those of the amended tests listed in the script's `AMENDED_TESTS` (§8.3). There may be no base-only keys. Plus the S08 and S10-C lines (S11.A23) and the existing `test_*identity*` tests |
| **G2 bases** | S11.A01–A10 |
| **G3 routing and refusals** | S11.A11–A15 |
| **G4 premises** | S11.A07–A08 numbers recorded in the manifest |
| **G5 verifier forms** | S11.A16–A19 |
| **G6 column in flowsheets** | S11.A20–A29, A35–A38, with timings (§4.12) |
| **G7 W27 v3 and the envelope** | S11.A30–A34, A40; `t08_support_matrix.py --check` |
| **G8 release-level** | full `scripts/gate.sh` PASS once, before merge; CI green on x86-64 and aarch64; Wilson and CoolProp compared across architectures by tolerance (worst relative deviation recorded) |

---

## 7. Risks and open questions (each with a default)

| Id | Question | Needs | Default |
| --- | --- | --- | --- |
| Q1 | Expose Wilson's repository-only records in source checkouts, with a typed refusal in a wheel (D11, against R-615's reasoning for `pr-lib-v1`)? | Frank's preference | **Yes** (R-811). Reversible: drop one registry row |
| Q2 | Pure-fluid thermal units (heater/cooler, pump/compressor/turbine with `s`, valve, mixer), with an ADR on two-phase pure-fluid streams under `nTP-v1` | Frank's preference (scope) | **S11b, next**; refused typed in S11 |
| Q3 | γ–φ EO faces for the K02/T05 units on Wilson (heater, flash, PH flash, valve, mixer) | Frank's preference (scope) | **S11c**; refused typed in S11 |
| Q4 | `pr-lib-v1` in flowsheets | Frank (R-615 ship decision) | **No** (R-809) |
| Q5 | CAS RNs in the new record files (L01 F-4 is open) | Frank's preference | **Include** water's and the S07 table's (already shipped in `src`); drop with F-4's clean-up if Frank rules them out (W27 then loses IAPWS-95 matching) |
| Q6 | Register a W27 `column` function against the OpenIDAES-450 archive | fact (workstation) | **Later**; `function: null` in v3 |
| Q7 | Does the binder require every multiplicity-1 port to be wired? | fact (WO-B2) | If yes: `top`/`bottom` multiplicity `many` with "at most one" in the unit |
| Q8 | Does the application accept `s01-default-v1` for a revision solve? | fact (WO-B3) | If no: register `s11-column-v1` = `S01_DEFAULT_V1` with a new id (an isolated commit) |
| Q9 | Does the region decomposition place stage pseudo-units with their rows without change? | fact (WO-B3) | If no: escalate to the design lane with the trace; no ad-hoc region surgery |
| Q10 | Does any verifier consumer need a stage split's instance beyond the prefix rule? | fact (WO-B4) | Resolve by the prefix; escalate if a consumer needs per-stage instance data |
| Q11 | A Wilson column with a `none` end (an absorber or stripper) | fact (B3) | Admitted if `solve_column` accepts it at library level; otherwise refused typed at bind (logged) |
| Q12 | Relax "one side feed per stage" (a two-phase feed then needs a flash and two stages) | Frank's preference | **Keep** S02's rule (L-COL-1) |
| Q13 | Unregistered `record_source` silently selects SYN-001 (ADR 0034 D8) | Frank's preference | **Keep**; tightening it would move identity |
| Q14 | Do the column cases exceed §4.12's time gate? | fact (B3) | Record; escalate before optimising |
| Q15 | The column's `F_ref` tolerance semantics (L-COL-6) | `specifier`'s judgement at review | **Accept**; the reviewer may ask for a scaled `F_ref` (a pinned instance parameter) |

**Risks.**
- Staged splits in the flowsheet region path are the least proven piece (Q9). WO-B3's first commit is a spike, A29
  on M1 alone, before anything else is built on it.
- The verifier changes in B4 follow A3 in time, so the schedule is serial there.
- Family C of G1 runs the suite twice: free compute, but slow. Run it in the background.

---

## 8. Records

### 8.1 ADR 0050 (Proposed)

`docs/adr/0050-s11-binding-package.md`. It changes `SELECTABLE_BASES`' element type and selection rule, and amends
ADR 0034 D8. It supersedes the library-only clauses of ADR 0045, ADR 0046 D9 and ADR 0047 D10–D11. It amends
ADR 0049 C4 (R-781's deferral is closed). No `Protocol` or schema changes.

### 8.2 The register

R-800…R-812 (numbering note: R-795 and R-796 are held by `wp/R796`; S11 starts at R-800).

### 8.3 Tests whose assertions S11 reverses on purpose (`AMENDED_TESTS`; each cites R-810 or R-805)

- `tests/test_m02_join.py:88-102` (A1, I1)
- `tests/test_t08_w2_support_envelope.py:61-80, 335-342` (A5, I1)
- `tests/test_s05_envelope.py:216-221` (A5; S05 A25)
- `tests/test_s07_registration.py:157-165` (A5)
- `tests/test_s10_provider.py:688-696` (A5; S10 A27)
- `tests/test_t05_w1b_revision.py:84` (I1: 14 `syn001.*`)
- `tests/test_t08_kinetic_cstr.py:217-218` (I1)
- `tests/test_t08_w2_unsupported.py` (the U04 column test; I1)
- `tests/test_t07_w5c_signatures.py` and `tests/test_t08_w2_edge_identity.py` sample tables (I1: the column's sample)
- `tests/test_m07a_harvest.py:56` (I2: `HARVEST_SIZE`)
- any `test_l01_*` assertion of `len(SELECTABLE_BASES) == 2` (A1; its `pr-lib-v1` clause stands)
- `tests/test_t08_b50_surface_content.py`, if its `list_models` surface pins the model set (I1 checks; it gains
  `syn001.column` only)
- *Erratum 2026-10-27:* two additions.
  - `tests/test_m02_wo8_registries.py::test_the_dormancy_registry_is_syn001s_and_the_c1_mixers_vapour_outlet`, which
    is restricted to keys outside `thermal.` (C6-2, R-839; no family-C key).
  - The syn001↔c1 refusal tests whose model gains an S11 basis (I1b, R-841).

### 8.4 Decisions logs

`docs/S11A_DECISIONS.md` and `docs/S11B_DECISIONS.md`, one line per decision.

---

## 9. Amendment, 2026-10-27: Frank's answers to Q2 and Q3 (design lane, `architect`)

On 2026-10-27 Frank answered §7 Q2 and Q3 with "Include in S11" for both. His directive is "as few limitations as
possible" (R-813). The sections below are amended in place by this section and are otherwise unchanged. The
normative text for the added scope is `docs/derivations/S11-units-design.md` (the units design), with ADR 0051 and
R-813…R-821.

- **§0 item 10 and D10.** The pure-fluid thermal units and the γ–φ faces of the K02/T05 units are **in S11**.
  - Pure-fluid streams are declared-regime: `vapor_liquid` means saturated, with a carried split (ADR 0051 D1–D3).
  - The new `thermal.*` family serves the pure-fluid bases.
  - On Wilson, `syn001.tp_heater`, `tp_flash`, `ph_flash`, `valve` and `adiabatic_mixer` are admitted by dispatch.
  - `wilson-ig-v2` adds `s`, for a vapour compressor and turbine on Wilson.

  What stays out: `pr-lib-v1` (R-809), NRTL/UNIQUAC/LLE, and the units design §1's out-of-scope list.
- **§4.4, the admission matrix.** The rows of the units design §4.7 are added. Its refusal reasons replace the two
  bullets that name S11b and S11c.
- **§4.4, "what each basis lacks":**
  - The Wilson `s` row is now closed by `wilson-ig-v2`; the isentropic machines are admitted on vapour, and the PS
    closures stay single-phase.
  - The Wilson `v`/`Z` row stays a refusal, now with the reason "the method's liquid has no volume (S10 §3.4)".
  - The IAPWS-95 and CoolProp row is closed: their two-phase states are the saturated form.
- **§7 Q2 and Q3** are answered. Their defaults (S11b, S11c) are superseded.
- **§4.1, §4.2, §4.3, §4.6 and §4.11** (Wilson provider id): from WO-D5, the Wilson record source selects
  `wilson-ig-v2`; `wilson-ig-v1` returns to `LIBRARY_ONLY_PROVIDERS` (units design §4.6). The count of 127 is
  unchanged.
- **§4.10, W27v3-R02 and R-08:** the row `wilson-ig-v2 → activity_coefficient` is added (v1's row is kept), and S4 is
  generated at I1b, not I1.
- **§5:**
  - I1 writes `MODEL_BASES["syn001.column"]` with the provider id that the Wilson registry row holds.
  - I2 also records G9–G13.
  - The per-commit identity trigger list gains `models/syn001/{tp_state,heater,flash,ph_flash,valve,mixer,
    equilibrium_form}.py`.
  - The integration WO I1b runs between I1 and I2.
- **§6.1 S11.A11 (erratum).** Compare the routing manifests with `implementation_artifact.artifact_hash` removed. That
  hash is `file_sha256` of the module (`tests/test_k02_unit_models.py:191`), so A2's edits to `feed.py`, `sink.py` and
  `splitter.py` necessarily move it.

---

## 10. Amendment, 2026-10-27: Q9 (stage splits in a flowsheet region) and three track-B escalations (design lane, `architect`)

Brief: `docs/briefs/S11-q9-ruling.md`. Facts: track B's Q9 spike (`docs/S11B_DECISIONS.md` on `wp/S11-b`) and the code
anchors in §10.1, all read at `wp/S11-b` `845faa48`. This section amends §2.3, §4.7.1, §4.7.3, §4.7.5, §5, §6 and §7
in place; everything else stands. Register R-822…R-827.

### 10.1 Facts the ruling rests on

- **F1.** `Region.units` is a list of flowsheet instances everywhere it is read. `build_region` places a row iff its
  authoring instance (`declaration.rows[row].unit`) is in `units` (`orchestrator/execution.py:418`).
  `plan_or_refusal` looks up `claimed[unit]` and `capable[unit]` for every unit of a specification region, and
  `capable` is keyed by `graph.units` (`execution.py:614-621`). `PlanStep.units` and `StepResult.units` are
  `region.units`.
- **F2.** The region solve keeps `split.unit in set(region.units)` (`orchestrator/region.py:1876`). Under v2,
  `_opening_order` indexes `at[split.unit]` with `at` built from `region.units` (`region.py:1061-1063`); a pseudo-unit
  that passed the filter would raise `KeyError` there.
- **F3.** The region solve never reads `region.signature_units`. It is plan identity: `SolvePlan.signature_units`,
  `_PLAN_IDENTITY` (`orchestrator/executor.py:567-575`), the replay projection (`run/identity.py:71`), and the
  schema types it as an array of non-empty strings. The attempt signature's lifted entries are
  `(split.unit, regime)` over the active splits (`region.py:1290`). Today `signature_units` equals those keys, in that
  order, for every registered flowsheet (instance ids) and for the standalone column (`column_solve.py:416-423`:
  stage keys).
- **F4.** The registry functions `zero_flow_forms`, `vapour_only_forms` and `split_temperatures`
  (`orchestrator/splits.py:341-420`) look up `models[split.unit]` and raise `KeyError` on a stage key. `_rule` and
  `_check_vapour_only_forms` tolerate one (they answer `_NO_RULE`).
- **F5.** `check_agreement` keys the `molar_flow_squared` rows by authoring instance (`splits.py:463-466`), and its
  check (f) compares `row_units[row]` with `split.unit` (`splits.py:555`).
- **F6.** `_resplit` (`orchestrator/revision.py:271`) re-splits the registry splits only. The column's stage columns
  enter the EO start through `UnitEvaluation.owned` (B2).
- **F7.** An instance id may contain `.` (`schemas/process-revision.schema.json:59`,
  `^[A-Za-z0-9][A-Za-z0-9_.:-]*$`). So `C1.stage.2` is a legal instance id beside a column `C1`.
- **F8 (premise error in §4.7.3).** `plan_revision` builds its region with no specification rows
  (`revision.py:400-405`). `continuation_parameter` returns `None` for a region without them (`homotopy.py:89`), so
  edge 3 on the revision path records `unsupported(no_continuation_parameter)` under `eo_recovery = "homotopy"` for
  every revision region. §4.7.3's "as for every other unit's pinned specification" does not hold there.
- **F9.** `TARGET_PATH_KINDS` generates the target-path table that the tool descriptions carry
  (`application/revision_binding.py:479-497`). A new pin path moves the served descriptions, which §2.2 forbids.
  `_PARAMETER_KINDS` is private (`models/revision_flowsheet.py:148`) and is read only by `required_kind` (`:541`)
  and `read_parameter` (`:701`), both keyed by the parameter name up to its first `.`.
- **F10.** `PinColumn` pins a column of the declaration: a stream quantity or the unit's duty
  (`revision_binding.py:195-210`). A reflux or boilup ratio, a purity and a recovery are not columns. They are
  constants of slot rows that the column itself authors.

### 10.2 The rule: split key and owner (Q9; R-822)

Every `LiftedSplit` has a **key**, `split.unit`, and an **owner**, the flowsheet instance that authored its rows.

- A registry split (`SPLIT_RULES`) is keyed by its instance, so its key is its owner.
- A **staged unit** is an instance whose rows describe several lifted splits.
  - Its model is in `orchestrator.splits.STAGED_MODELS`, which is `frozenset({"syn001.column"})` in S11 and is
    disjoint from `SPLIT_RULES`.
  - The instance supplies its splits as one `StagedSplits` value, through its method `staged_splits()`.
  - Its keys are opaque strings, each owned by the instance. The column's keys are `stage_unit(U, j)`, the standalone
    keys.
  - A key must differ from every other key and from every instance id of the revision.
- The **owner map** `owners: key → instance` lists the staged keys only, and `owner(split) = owners.get(split.unit,
  split.unit)`. The staged unit supplies the map; it is never derived from id text (R-019).

| Keyed by the split key | Keyed by the owner |
| --- | --- |
| closure types, zero-flow forms, split temperatures, vapour-only forms, regimes, PH units, F2 records, the attempt signature's lifted entries, `signature_units` | region membership, row authorship (`row_units`), the opening position, dormancy forms, `Region.units`, `PlanStep.units`, capability, step reports |

- **Region membership.** A split is active in a region iff `owner(split) ∈ region.units`. `build_region` places a row
  iff its author is in the region (F1), so this is exactly §4.7.5's "the region that holds its equilibrium rows".
  `Region.units` stays a list of flowsheet instances.
- **Opening order (v2).** `_opening_order` keys a split by `(index of owner(split) in region.units, 0, k)`, where `k` is
  the split's index in the active splits. So a staged unit's splits sit at its declaration position, in the order
  supplied. For the column that is `spec.equilibrium_stages()` order, as in the standalone solve. They are followed
  by the unit's dormancy-form outlets (the column has none).
- **`signature_units`.** These are the region's units that author a `molar_flow_squared` row, in region order
  (`_lifted_units`, unchanged), with each staged instance replaced, in place, by its keys in the order supplied. The
  invariant is `region.signature_units == tuple(split.unit for split in active splits)` (F3). Step 5 below guards it.
- **Declaration order of the splits.** `lifted_splits(instances, components, *, staged=None)` works per instance:
  - an instance whose model is in `SPLIT_RULES` contributes its descriptor;
  - an instance whose id is in `staged` contributes `staged[id].splits`;
  - an instance in both raises `ValueError(staged_unit_has_rule(<U>))`.

  `staged=None` and `staged={}` give today's output.

**The code, exactly:**

1. **`orchestrator/region.py`** gets a frozen dataclass `StagedSplits`, beside `LiftedSplit` and `ZeroFlowForm` (no new
   import edge for the models). Its fields:
   - `splits: tuple[LiftedSplit, ...]`;
   - `closure_types: Mapping[str, ClosureType]`;
   - `zero_flow_forms: Mapping[str, ZeroFlowForm]`;
   - `split_temperatures: Mapping[str, tuple[str, ...]]`;
   - `other_squared_rows: tuple[str, ...]`: the instance's `molar_flow_squared` rows that are no split's equilibrium
     rows (§10.3).

   `__post_init__` raises `ValueError` unless `splits` is non-empty, its keys are pairwise distinct, and the key sets
   of the three maps each equal the set of keys. There are no vapour-only forms: a staged unit that needs them is a
   design-lane amendment.
2. **`solve_region(..., split_owners: Mapping[str, str] | None = None)`.** Let `owners = split_owners or {}` and
   `inside = set(region.units)`. Line 1876 becomes
   `active_splits = [split for split in splits if owners.get(split.unit, split.unit) in inside]`. Line 1899 passes
   `owners` to `_opening_order(active_splits, dormancy, region.units, owners)`, whose key is
   `(at[owners.get(split.unit, split.unit)], 0, k)`. Nothing else in `region.py` changes.
3. **`orchestrator/splits.py`:**
   - `STAGED_MODELS`.
   - `staged_units(units) -> dict[str, StagedSplits]`: `unit.staged_splits()` for each unit whose `model_id` is in
     `STAGED_MODELS`, in declaration order.
   - `split_owners(staged) -> dict[str, str]`.
   - `lifted_splits(..., staged=None)`, as above.
   - A frozen `RegionSplits` and `region_splits(instances, units, components) -> RegionSplits`. This is **the only
     place the merge is written**:

     ```
     staged   = staged_units(units)
     registry = lifted_splits(instances, components)            # registry functions take these only (F4)
     types    = closure_types(units)
     RegionSplits(
       splits             = lifted_splits(instances, components, staged=staged),
       owners             = split_owners(staged),
       staged             = staged,
       closure_types      = {**types, **⋃ s.closure_types},
       zero_flow_forms    = {**zero_flow_forms(instances, registry, types, components), **⋃ s.zero_flow_forms},
       split_temperatures = {**split_temperatures(instances, registry), **⋃ s.split_temperatures},
       vapour_only_forms  = vapour_only_forms(instances, registry, components))
     ```

     Here ⋃ runs over `staged.values()` in declaration order.
4. **`build_region(..., staged_units: Mapping[str, tuple[str, ...]] | None = None)`** (`execution.py`):
   `signature_units = tuple(key for unit in _lifted_units(declaration, units) for key in (staged_units or
   {}).get(unit, (unit,)))`. Its other callers pass nothing.
5. **`plan_revision`** (`orchestrator/revision.py`):
   - `rs = region_splits(instances_of(flowsheet), flowsheet.units(), flowsheet.components)`.
   - `check_agreement(instances, rs.splits, spec, binding.row_units, declaration, rs.zero_flow_forms,
     dormancy_forms(...), rs.vapour_only_forms, staged=rs.staged)`.
   - `whole = build_region(..., staged_units={u: tuple(s.unit for s in st.splits) for u, st in rs.staged.items()})`.
   - The guard: if `whole.signature_units != tuple(split.unit for split in rs.splits)`, raise
     `ValueError("signature_units_disagree: plan […], splits […]")`. The region holds every author, and by
     check (a′) every owner authors a row, so the right-hand side is every split.
6. **`executor.py`.** The revision branches of `_splits`, `_closure_types`, `_zero_flow_forms`, `_split_temperatures`
   and `_vapour_only_forms` return the matching `region_splits(...)` field. A new `_split_owners(flowsheet)` is `{}`
   for `Syn001Flowsheet` and `.owners` otherwise. The single `solve_region` call (`executor.py:1069`) passes
   `split_owners=_split_owners(flowsheet)`. The `Syn001Flowsheet` branches, `_dormancy_forms` and `_mass_mapping` do
   not change.
7. **`models/syn001/column_unit.py`.** `column_staged_splits(structure) -> StagedSplits` builds from
   `structural_spec(structure)` with `column_solve.lifted_splits`, `closure_types`, `zero_flow_forms` and
   `split_temperatures` (§4.7.2's permitted uses). Its `other_squared_rows` are the definition row of each `purity`
   end (S06's id) and of each `recovery` end (`<U>:stage:<j>:spec:recovery_definition`), condenser first; it is
   empty otherwise.
   - The builder (`application/column_binding.py`) computes it once and the `ColumnUnit` holds it as a field.
     `staged_splits()` returns that field. There is no module-level cache (`test_t07_global_state` G20).
   - The verifier calls the same pure function (§10.11, B4).
8. **`_resplit` does not change** (F6): it stays registry-only.
9. **Bind-time key check (I1, `revision_binding.py`).** After every unit is built, the binder refuses any instance id
   in `split_owners(staged_units(units))` as `id_unsupported(<id>)`. The hint is: "Instance id `<id>` is a
   lifted-split key of instance `<U>`; rename the instance." This is a set intersection of supplied keys with ids, not
   parsing. Until I1 the column is reachable only through the tests' monkeypatched builder, and check (a″) (§10.3) is
   the backstop.

**Identity argument.** No registered flowsheet holds a staged unit, so `staged == {}` and `owners == {}` there, and
every changed expression reduces to today's:
- `lifted_splits(..., staged={})` is `lifted_splits(...)`, so `rs.splits is`-equal to `registry`;
- every `{**m, **{}}` equals `m` with the same key order. The three registry functions receive the same arguments as
  today (`executor` passed `_splits(fs)` and `closure_types(units)`; `plan_revision` passed `splits` and
  `closure_types(flowsheet.units())`);
- `owners.get(k, k) == k`, so the filter predicate and the `_opening_order` keys are unchanged;
- `(staged_units or {}).get(u, (u,)) == (u,)`, so `signature_units` is unchanged;
- `check_agreement(staged=None)` takes no new branch, its messages are unchanged, and (a″) cannot fire, because the
  keys are distinct instance ids;
- the guard holds by construction. `_lifted_units` lists the authors with a squared row in `flowsheet.units()` order.
  The registry splits list the instances with a rule in `instances_of` order, which is the same order. Check (a)
  proves the two sets equal;
- `Syn001Flowsheet`, `compile_column` (standalone), `cascade_solve` and `tear` call `solve_region` without
  `split_owners`, and `build_region` without `staged_units`.

The proof is this argument together with `scripts/s11_identity.py`: `changed=[]`, no base-only keys, and `n ≥ 54497`
because new tests add keys. The S08 and S10-C lines must reproduce, and the touched test files must pass (§10.12).

### 10.3 `check_agreement` with staged splits (R-823)

`check_agreement(..., staged: Mapping[str, StagedSplits] | None = None)`. Let `owners = split_owners(staged or {})`,
`Q(U)` be U's `molar_flow_squared` rows in `equation_ids` order (as today), and `E(U)` the union of the equilibrium
rows of U's staged splits.

- **(a′)** The units in `Q` are exactly `{owner(s) for s in splits}`. A unit with no descriptor raises
  `lifted_split_unregistered(<model>)` (as today), and a split whose owner has no squared rows raises
  `lifted_split_without_rows(<key>)` (as today).
- **(a″)** The keys `[s.unit for s in splits]` are pairwise distinct, and no staged key is an instance id. Otherwise
  it raises `lifted_split_key_collision(<key>)`.
- **(b)** For a registry split: unchanged.
- **(b′)** For a staged instance U:
  1. For each of its splits `s`, `tuple(r for r in Q(U) if r in set(s.equilibrium_rows)) == s.equilibrium_rows`.
     Otherwise it raises `lifted_split_rows_disagree(<key>)`, naming both lists.
  2. The equilibrium rows of U's splits are pairwise disjoint, they are disjoint from `staged[U].other_squared_rows`,
     and `set(Q(U)) == E(U) ∪ set(other_squared_rows)`. Otherwise it raises `staged_split_rows_disagree(<U>)`, naming
     the unclaimed rows and the claimed rows that U did not author.
- **(c)–(e), (g), (h):** unchanged, applied to every split. A stage key answers `_NO_RULE`.
- **(f′):** `foreign = [row for row in form.rows if row_units.get(row) != owner(split)]`. The rest is unchanged.

`other_squared_rows` is the unit's own independent statement. The check therefore keeps today's invariant that no
`molar_flow_squared` row is unclaimed, and an omitted stage descriptor still raises. If (c)–(f′) fails on the
column's own descriptors, stop and escalate with the message (Q28). Never relax the check.

### 10.4 Rejected for Q9

- **Stage keys in `Region.units`.** This breaks `plan_or_refusal`'s `capable[unit]` and `claimed[unit]` lookups (F1),
  and it puts pseudo-units into `PlanStep.units`, the step reports and every consumer that treats `units` as
  instances.
- **Resolving a stage key to its instance by the `.stage.` prefix.** R-019 forbids deriving an author from id text,
  and F7 makes the parse ambiguous. This also replaces §7 Q10's prefix default (§10.11, B4).
- **An `instance` field on `LiftedSplit`.** It would move `LiftedSplit`'s registered `repr` digest. The project keeps
  per-split facts in maps beside the descriptor (`zero_flow_forms`, `split_temperatures`, `vapour_only_forms`), and the
  owner map follows that pattern.
- **Exempting staged units from (a)/(b).** That silently admits an unclaimed equilibrium row, which is the Q9 failure
  itself.
- **Duck-typing `getattr(unit, "staged_splits", None)` instead of `STAGED_MODELS`.** A registry keyed by model id
  mirrors `SPLIT_RULES` and is robust to test stand-ins, whose `getattr` answers a callable.

### 10.5 End specifications are instance parameters (R-824)

The end specifications are **instance parameters**, as track B built them. They are renamed so that the name up to the
first `.` fixes the kind (R6):

| Parameter | Kind | Parameter | Kind |
| --- | --- | --- | --- |
| `condenser_reflux_ratio` | dimensionless | `reboiler_boilup_ratio` | dimensionless |
| `condenser_distillate_rate` | molar_flow | `reboiler_bottoms_rate` | molar_flow |
| `condenser_duty` | heat_rate | `reboiler_duty` | heat_rate |
| `condenser_purity.<component>` | dimensionless | `reboiler_purity.<component>` | dimensionless |
| `condenser_recovery.<component>` | dimensionless | `reboiler_recovery.<component>` | dimensionless |
| `condenser_temperature.<stage>` | temperature | `reboiler_temperature.<stage>` | temperature |

- `end_entries` reads the names that start with `condenser_` or `reboiler_`.
- The kind is the rest of the first segment, and the attribute follows the `.`.
- Two names at one end raise `specification_conflict(<U>.<end>)`, as now. Any other `condenser_*`/`reboiler_*` name,
  and any dotted `condenser.`/`reboiler.` name, raises `parameter_unsupported(<U>.<name>)`.
- A `role: fixed` specification with target path `parameters.<name>` lands here, as before.
- The slot rows keep S02/S06's ids and `"<column>*"` parameter names; their values come from these parameters.
- `_COLUMN`'s signature lists the twelve as optional parameters.
- §4.7.1's `SpecificationChoice` sentence and its pin-encoding sentence are withdrawn, and so is §4.7.3's last
  paragraph (§10.8).

**Rejected:**
- **Pins.** A pin pins a column, and ratios, purities and recoveries are constants of the column's own slot rows
  (F10). New pin paths would move the served tool descriptions (F9, §2.2). Pins would also need track A's `_read` and
  a non-stream `PinQuantity`. And A24 does not follow from them on the revision path anyway (F8).
- **Dotted `condenser.<kind>`.** R6 types a parameter by its first segment, so typing these would need a two-level
  lookup rule in track A's `read_parameter` and `required_kind`.

### 10.6 `_PARAMETER_KINDS` (R-825)

**I1** adds sixteen entries to `models/revision_flowsheet.py` `_PARAMETER_KINDS`:
- `stage_count`: dimensionless;
- `stage_pressure`: pressure;
- `feed_stage`: dimensionless;
- `stage_duty`: heat_rate;
- the twelve names of §10.5.

These are data only; the lookup rule does not change. `_PARAMETER_KINDS` feeds no served text (F9), and no existing
key collides.

Why I1:
- the file is track A's (A1), and A is building now;
- until I1 the column is reachable only through the tests' monkeypatched builder;
- B3's cases write SI values of the right declared kind, so they do not depend on the table.

### 10.7 `models/rows.py` (R-826)

Accepted. B1's `scaled_sum_definition_row` is a new function, and no existing builder changes.
- `test_k02_unit_models` forbids row builders in unit modules, so `rows.py` is their home.
- Track A does not touch it, and tracks C/D use `models/thermal/rows.py`.
- `models/rows.py` is added to B1's file list retroactively. It is track B's until B merges. After that, any WO may
  add a function to it, but may not edit an existing one.
- The per-commit identity trigger list (§5) gains `models/rows.py`.

### 10.8 A24 and edge 3 on the revision path (R-827)

F8 voids A24's premise. Giving revision regions specification rows would change every revision plan and send the
executor down the promoted-specification path (`executor.py:670`), which is outside S11.

- **S11.A24′** replaces A24. On the M1 column revision, `region.specification_rows == ()` and
  `continuation_parameter(...) is None`, exactly as for a registered T05 heater→flash revision.
- New limitation **L-COL-9**: "In a flowsheet a column region has no edge-3 continuation (no revision region has one).
  The unit's own `evaluate` keeps S02's full standalone path, S08 Stage B included, so the traversal start is the
  standalone answer."
- §4.7.3's sentence that WO-B3 checks the binder's promotion naming is withdrawn.

### 10.9 Interaction with the units design's C6/D6 spikes (Q18)

There is no functional interaction. The thermal units author no `molar_flow_squared` row, and the Wilson K02/T05 units
are registry splits, so their key equals their owner and §10.2 is inert for them.

The file order is as follows:
- B3a is the only S11 commit that edits `region.py`. If Q18 ends in a region ruling, that work rebases on it.
- C6's `splits.py` entries (`_CONFIGURED_BY`, `DORMANCY_RULES`) come after B3 merges, as the units design §4.9
  already says, and touch other functions.

### 10.10 File ownership

| File | Change | WO (track) |
| --- | --- | --- |
| `orchestrator/region.py` | `StagedSplits`; `split_owners`; line 1876; `_opening_order` key | B3a (B) |
| `orchestrator/execution.py` | `build_region(staged_units=)`, `_lifted_units` expansion | B3a (B) |
| `orchestrator/splits.py` | `STAGED_MODELS`, `staged_units`, `split_owners`, `lifted_splits(staged=)`, `RegionSplits`/`region_splits`, `check_agreement(staged=)` | B3a (B) |
| `orchestrator/executor.py`, `orchestrator/revision.py` | §10.2 steps 5–6 | B3a (B) |
| `models/syn001/column_unit.py`, `application/column_binding.py` | `column_staged_splits`, the held field; end-parameter names | B3a, B3b (B) |
| `models/rows.py` | (done) | B1 (B), accepted |
| `models/revision_flowsheet.py` | sixteen `_PARAMETER_KINDS` entries | I1 |
| `application/revision_binding.py` | the key check, §10.2 step 9 | I1 |
| `verify/table.py`, `verify/zero_flow.py`, `verify/certificate.py` | the owner map | B4 (B) |
| `benchmarks/t08/support_envelope.yaml`, `docs/support-matrix.md` | L-COL-9 (L-COL-1…9) | I1 |

### 10.11 Revised work orders

**B3** (replaces §5's B3 row). Depends on B2. Commits, in order:
- **B3a: staged splits** (R-822, R-823). §10.2 steps 1–8, §10.3, and the new `tests/test_s11_staged_splits.py`
  (A87–A90). Acceptance:
  1. Rerun the spike (`column_revision(SPECS["M1"])`, `plan_revision`, `execute_plan` under `S01_DEFAULT_V1` passed as
     the policy object). It must end converged, with A29's M1 numbers.
  2. The §10.12 per-commit check.
- **B3b: end-parameter names** (R-824): `column_unit.end_entries`/`_end_specification`, `END_PREFIXES`, `_COLUMN`'s
  parameters, and the B1/B2 tests and support. Acceptance: A92, and B1/B2's tests pass renamed.
- **B3c:** Q8's `s11-column-v1` registration (isolated, as §4.7.5).
- **B3d:** A28's policy check.
- **B3e:** the cases (`benchmarks/s11/flowsheets/*.json`, `tests/test_s11_column_solve.py`): A29, A24′, Q11, the Q14
  timings, and the Q29 record.

**B4.** §7 Q10's default is replaced:
- for each instance whose model is in `STAGED_MODELS`, the verifier builds
  `column_staged_splits(column_structure(view, components))`, and passes the result to its `lifted_splits(...,
  staged=)` call (`certificate.py:706`) and to `split_owners`;
- `table.py:1531` and `zero_flow.py:149` look up `instances[owner(split)]`;
- a consumer that needs per-stage instance data beyond the owner is escalated.

**I1** gains:
- R-825's sixteen entries and A93;
- §10.2 step 9 and A91;
- L-COL-9 in the envelope.

**§5 trigger list** gains `models/rows.py`.

### 10.12 Assertions and gates

- **S11.A87 (inert).** On the M02 flash revision and one T05 heater→flash revision, `region_splits(...)` gives
  `splits == lifted_splits(instances, components)` and `owners == {}`. Each map equals, with the same key order, the
  registry function's output for the same arguments.
- **S11.A88 (placement).** On M1:
  - the plan's `solve_eo` `units` holds no stage key;
  - `signature_units == tuple(stage_unit("UCOL", j) for j in equilibrium stages)`;
  - the active splits number N_eq;
  - attempt 0's lifted signature keys equal `signature_units`, in order.
- **S11.A89 (agreement defects).** Each of the following raises its named `ValueError`:
  - a `StagedSplits` missing one stage;
  - a recovery case whose `other_squared_rows` misses its definition row;
  - a staged key equal to an instance id;
  - an instance in both registries.
- **S11.A90 (guard).** On M1, a region built without `staged_units` makes the guard raise
  `signature_units_disagree`.
- **S11.A91 (I1).** Column `C1` beside an instance `C1.stage.<j>`, for j an equilibrium stage, is refused at bind as
  `id_unsupported(C1.stage.<j>)`.
  *Erratum 2026-10-27 (R-838):* the revision reader's id rule (`revision_flowsheet.py:83`) refuses the dotted id
  before binding. §10.2 step 9 remains the binder's guard, exercised by A89(3). See `docs/reviews/S11-rulings.md` item 9.
- **S11.A92 (B3b).** Each of the twelve names configures its `EndSpecification`. `condenser.reflux_ratio` raises
  `parameter_unsupported(<U>.condenser.reflux_ratio)`. Two `condenser_*` names raise `specification_conflict(<U>.condenser)`.
- **S11.A93 (I1).** Each of the sixteen names with a wrong declared kind raises `parameter_kind_unsupported(<U>.<name>)`.
  `stage_pressure.1` given in `bar` reads as `unit-conversion-v2`'s Pa value, `float.hex`-equal.
- **S11.A24′:** §10.8.
- **Per-commit check for B3a** (batched, one run): `scripts/s11_identity.py` in the background with one wait, giving
  `S11-IDENTITY PASS changed=[]` with the S08 and S10-C lines, plus pytest on
  `$(grep -lE 'solve_region|check_agreement|lifted_splits|build_region|plan_revision|_opening_order' tests/test_*.py)`
  (76 files at `845faa48`) and `tests/test_s11_*.py`. No new gate.
- **G6** gains A87–A90, A92 and A24′. I1's acceptance gains A91 and A93.

### 10.13 Open questions (each with a default)

| Id | Question | Needs | Default |
| --- | --- | --- | --- |
| Q9 | answered by §10.2 (R-822) | — | — |
| Q10 | superseded by the owner map (§10.11, B4) | — | Escalate a consumer that needs more than the owner |
| Q28 | Do (c)–(f′) hold on the column's own stage descriptors (definition-row incidence, label, swapped row)? | fact (B3a) | Expected yes: the standalone solve reads the same descriptors and forms. If not, stop and escalate the message; never relax |
| Q29 | A column under a PTC policy (`eo_core = "ptc"`): typed `PTC_MAPPING_INVALID`, or a mapping? | fact (B3e) | Record the outcome. A typed refusal is accepted as L-COL-10 at I1; an exception is escalated |
| Q30 | An edge-3 continuation for revision regions (column slot rows included) | Frank's preference (scope) | **Not in S11** (L-COL-9); a follow-up package |
| Q31 | Spelling of the end parameters: `condenser_reflux_ratio` or dotted with a two-level kind lookup | Frank's preference (taste) | **Underscore** (R-824). Reversible: one rename in `column_unit` plus a lookup-rule change in track A's file |
| Q32 | Does any of the sixteen new `_PARAMETER_KINDS` names occur on another model in the suite's documents? | fact (I1, family C) | Expected none. A changed family-C key is a refusal-code change on a registered document: stop and escalate |
