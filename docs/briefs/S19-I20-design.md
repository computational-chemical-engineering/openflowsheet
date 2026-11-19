# S19 I-20 design: the verify twins under one parameter object

**Lane:** design (`architect`). **Brief:** `.git/codehealth/briefs/S19-A-I20.md`. **Base:** `wp/S19` 356ee519.
**Authority:** Frank, Decision Desk `ofs-s19-verify-twins`, choice A (2026-11-19, verified); ADR 0076 addendum I-20
(same commit as this note). **Binding:** `docs/S19_RULES.md`, `.codehealth/playbook.md`, ADR 0076 "Rules that bind
every W4 step" and "Per item". Every number below was measured at 356ee519 unless it says "predicted".

## 1. Problem and scope

`verify/gamma_phi_units.py` (health 6.4) and `verify/pr_c1.py` (7.7 at the tip; the brief's 6.7 is older) are the
verifier's per-form modules for the γ–φ (`wilson-ig-v2`) and PR (`pr-c1-v1`) bases. Their twins:

- **T1, the check set.** `gamma_phi_units.revision_checks` (gamma_phi_units.py:372, 8 params, debt 10.8) is
  `table.revision_checks`' declared-mixture path with three substitutions: a provider guard (:390), the γ–φ
  degeneracy, and the registry splits' rows ahead of the stream rows (:477-488). The 42 lines it shares with table.py
  give both files the duplication smell (gamma_phi_units 59 dup lines = 15%, table.py 42 = 12.9%).
- **T2, the split checks.** One function per form with one signature: `split_checks._split_checks` (SYN,
  split_checks.py:51, 9 params), `pr_c1.split_checks` (:280, 7), `gamma_phi_units.split_checks` (:295, 8). Same ids,
  same independent-split rows, same degenerate pair; different physics in between.
- **T3, the declared ports.** `pr_c1.declared_port_checks` (:393; cognitive 21, nesting 4) re-implements
  `split_checks._declared_streams` (:304) over a passed-in ports table.

In scope: one parameter object for the split family; T1 merged into `table.revision_checks`; T2 and T3 sharing their
rows through the kit; the R-W3-G5-3 fix 1 (`_Routing` built by keyword) landing with the routing phase that T1 needs.

Out of scope (signatures unchanged; default for each in section 9): the three degeneracy functions
(`split_checks.degeneracy`, `gamma_phi_units.degeneracy`, `table._mixture_degeneracy`), `forms.stream_admissibility`,
`thermal.saturated_stream_checks`, `pr_c1.band`, `pr_c1._phase_property`, `gamma_phi_units._phase_flow`, `Unit`'s
fields, every check id, message, tolerance and order, and the S11.A73 test semantics (finding F1, section 9).

## 2. Measured facts

| file | health | debt | penalty parts (report.py weights) |
|---|---|---|---|
| verify/gamma_phi_units.py | 6.4 | 19.0 | complex 2 (degeneracy 17, revision_checks 19) 1.0; long 2 (split_checks 72, revision_checks 108) 0.6; many_args 5 (cap) 1.0; duplication 1.0 |
| verify/pr_c1.py | 7.7 | 23.4 | complex (declared_port_checks 21) 0.5; long (split_checks 104) 0.3; deep_nesting (declared_port_checks 4) 0.5; many_args 6 (cap) 1.0; dup 33 = 9.3% (25 with split_checks.py, 8 with gamma_phi_units) |
| verify/table.py | 8.8 | 3.0 | many_args (revision_checks 8) 0.2; duplication (42 lines, all with gamma_phi_units) 1.0 |
| verify/split_checks.py | 8.7 | 16.2 | long (_split_checks 72) 0.3; many_args 7 (cap) 1.0 |
| verify/table_kit.py | 10.0 | 0 | none |

Repo scan: 329 files, debt 3439.5, health 8.46. `codehealth arch --depth 4`: 329 files, 4107 imports, 0 violations,
0 cycles.

**Callers inventory** (grep over src, tests, scripts, benchmarks, examples):

- src: verify/table.py:43 (`pr_c1`), :128-142 (γ–φ dispatch: lazy import :131, call :133), :157 (`_Routing(...)`
  positional), :160 (`_Judging(...)`), :272 (`pr_c1.enthalpy_flow`, unchanged), :403 (`pr_c1.split_checks`), :406
  (`pr_c1.declared_port_checks`), :412 (the ports comprehension), :430 (`_split_checks`), :441
  (`_declared_port_checks`); verify/gamma_phi_units.py:478 (its own `split_checks`); verify/certificate.py:406, :494
  (lazy import and call of `table.revision_checks`, unchanged); verify/flowsheet_rows.py:14, :70, :112-113 and
  verify/unit_checks.py:25, :180, :411, :791 (read `pr_c1` constants only, unchanged); docstrings
  verify/table_kit.py:6, verify/forms.py:4, :53.
- tests: tests/test_s11_gp_verifier.py:80 (import), :293 (`gp_checks`), :359 (A73 routing), :378 (A73 column, inside
  `both`), :493 (guard test); unchanged uses :326 (`BAND_NOTE`), :445 (`degeneracy`), :485, :487 (`registry_splits`).
  tests/s11_gp_support.py:35 (import), :275-287 (`count_gamma_phi`: :278 `original = gamma_phi_units.revision_checks`,
  :286 `monkeypatch.setattr(gamma_phi_units, "revision_checks", counted)`), docstring :7-10; its fixture in
  tests/test_s11_gp_solve.py:77-78, asserted at :108 (`dispatched and all(count > 0 ...)`). tests/test_m02_wo8_verifier.py:42
  (import), :171 (`split_checks`), :230, :238 (`declared_port_checks`); unchanged :90 (R-016 source read of
  verify/pr_c1.py), :120, :126, :127 (`band`), :255, :271 (`enthalpy_flow`). Unchanged: tests/test_m02_wo8_g7.py:45,
  :265, :267; tests/test_st_core.py:56, :1035, :1741-1746; tests/test_m02_wo9_reactor.py:55, :426, :428.
  Source-reading: tests/test_t05_table_independence.py:45-51 `TABLE_MODULES` already covers table.py, table_kit.py
  and split_checks.py, the only files that receive moved code.
- scripts, benchmarks, examples: none (every `pr_c1` there is `thermo.pr_c1`).
- Patches of the private names touched here (`_Judging`, `_Routing`, `_declared_streams`, `_DeclaredStream`,
  `_degenerate_split_checks`, `_split_admissibility`, `_fresh_dew`, `_closure`, `_instance_rows`,
  `_stream_enthalpies`, the `_*_admissibility` helpers): none. Form patches that keep working unchanged:
  tests/test_s19_component_order.py:48 and tests/test_t05b_zero_flow.py:273 (`setitem(forms._FORMS, ...)`).
- **Frozen:** none of the 35 M9 modules (`scripts/codehealth_frozen.py`) and no registry-hashed file imports
  `verify.gamma_phi_units` or `verify.pr_c1`; no I-20 change waits for W5.

Two facts the design rests on: `forms.pure_fluid_provider(p)` is `not composition_dependent(p)` (forms.py:74-79), so
on the γ–φ path, which the guard admits only for a composition-dependent provider, the saturated set is empty; and
`WilsonIdealGasProviderV2.describe` (thermo/wilson_ig_v2.py:130-140) builds a new record from constants (pure).

## 3. Constraints and invariants

- **Bitwise identity** (S19_RULES): same CheckResult ids, values (`float.hex`), messages, order; same exceptions;
  same order of provider evaluations. Tier S2 (`verify/**`), but the S1 arithmetic rule is applied anyway: no float
  expression is rewritten, reassociated or hoisted across another float expression; every value below is computed by
  today's expression on today's operands in today's order.
- **R-016:** the verifier never goes through the solver (forbid rule `verifier-not-through-the-solver`); the table
  rule of tests/test_t05_table_independence.py holds for every module in `TABLE_MODULES`; test_m02_wo8_verifier's
  `violations(pr_c1 source)` stays exactly the one `TAU_DEW` import.
- **Layering:** `openflowsheet.verify` is one layer entry; no new module; arch 0 violations and 0 cycles at every
  commit. No cycle: `pr_c1` may not import `split_checks` or `unit_checks` (unit_checks.py:25 imports `pr_c1`), so
  anything `pr_c1` shares lives in `table_kit` (imports only `checks`, the package root, ids, views, thermo).
- **Interface gate** (ADR 0076 rule 1): a removed name survives in no form; a caller file only follows the plan (a
  statement naming a changed name may be rewritten into one of the same kind; no new statements, so no new imports);
  `__all__` changes only by the plan's names.
- **No shims:** no alias, re-export, wrapper or `__getattr__` for a removed or changed name, at any commit.

## 4. The decision

**D1. One parameter object, `Judging`, in `verify/table_kit.py`** (the kit every form module already imports, and
the only home `pr_c1` can import without a cycle). Exactly the six fields R-W3-G5-3 named, with `Unit`'s names and
types for the same values. A frozen dataclass, not a NamedTuple: no positional unpacking (R-W3-G5-12 asked for field
reads), built by keyword at its one production site.

**D2. The twin difference is carried by a strategy field: the resolved `form`** (`forms.Form`, already a Literal,
already resolved from the basis by `forms.form_of`), read at exactly two sites of `table.revision_checks`: the
routing phase and the admissibility dispatch. Each rung calls its own form's functions. Rejected:

- *Two thin entry points* (keep `gamma_phi_units.revision_checks` over a shared core). `gamma_phi_units` cannot import
  table.py (table imports it), so the core would need a new module holding most of table.py, and both entries would
  keep a copy of the prelude (`at`, notes, reacting) and of the category-major assembly. More structure, the same
  result, and the γ–φ entry's only callers besides the dispatcher are tests that already reach it through the
  dispatcher with the same arguments (F1).
- *A small per-form table* (`FORMS[form] -> (routing, admissibility)` callables). The rungs read different routing
  results (SYN reads `enthalpy` and `degenerate`, PR neither, the mixture form `saturated`), so one signature would
  pass every rung arguments it ignores and hide which form reads what (S19_RULES rejected: hiding branches in data
  structures; playbook parameter-object "when not").
- *One split-check function with a method field.* The forms compute different things (K-value bubble, dew and
  closure; provider stability `tm`; the NH3 dew band and first-order closure), so it would be three bodies behind a
  kind flag (playbook accepted forms: sibling builders share a parameter list, never one builder with a kind flag).
  What the three share verbatim is their rows; those move to the kit (D3).

**D3. Shared rows in the kit**: `degenerate_split_rows` (SYN's `_degenerate_split_checks`, moved),
`independent_split_rows` (the `.total` and per-component rows all three forms build), `DeclaredStream` and
`declared_streams` (SYN's iterator, moved, taking the ports table PR's test injects).

**D4. `_Routing` is not absorbed into `Judging`.** `Judging` holds inputs known before any evaluation; `_Routing`
holds the routing phase's results (the degeneracy calls the provider). One object would be partly filled between
phases (playbook parameter-object "when not", S17 review 3). `_Routing` keeps its five fields and is built by keyword
in the new routing phase `_routing` (R-W3-G5-3 fix 1, which raised debt alone and now lands with the phase).

**D5. `Unit` is not rebuilt on `Judging`.** 69 field reads in unit_checks.py, thermal.py and column.py, the `_Unit`
Protocol (column.py:113), the per-category `replace(judged, state=state)` (table.py:357) and test constructions of
`Unit` would all change for no health gain. Reconciliation is by name and type: `state`, `components`, `provider`,
`context`, `tolerances` mean the same in both; `Unit.energy_note` is `note` or `note + REACTION_DATUM_NOTE`.

**D6. `reaction_note` stays out of `Judging`** (the review's six fields; only the instance energy rows and the
envelope read it). `_instance_rows` takes it explicitly (6 params, debt +1.0 on table.py, accepted).

## 5. The design

### 5.1 `Judging` (table_kit.py, directly after `Unit`)

```python
@dataclass(frozen=True)
class Judging:
    """What a check of the split family judges with (T05 design note §4.3; ADR 0013 D1): the state the
    fresh-flash checks read, the order a stream's flows are read in, the fresh provider and the
    declaration's context, the tolerances by kind and the provider's qualification note. Its fields
    carry `Unit`'s names for the same values."""
    #: `judged_at` (ADR 0013 D1; K04-F9 spec §5.1), or the certified state when that is `None`.
    state: Mapping[str, float]
    #: The revision's component order (`RevisionView.components`; M02 design note §14.2 B15 item 1).
    components: tuple[str, ...]
    provider: PropertyProvider
    context: EvaluationContext
    tolerances: Mapping[str, float]
    #: `checks.qualification(provider)` (A09).
    note: str
```

No defaults, no methods. Production construction, once, in `table.revision_checks`:
`Judging(state=at, components=view.components, provider=provider, context=context, tolerances=tolerances, note=note)`.
`Unit`'s docstring gains one sentence naming the shared fields.

**Parameter convention:** `judging` is the last positional parameter; optional and keyword-only parameters follow it.
Where a function took `components` as a parameter it reads `judging.components`; where it read `view.components`
it keeps doing so (equal by construction: the table builds `components=view.components`).

### 5.2 Signatures (step a unless marked b or c)

| function | today | after |
|---|---|---|
| gamma_phi_units.split_checks | (split, components, state, provider, context, tolerances, note, distance=None) | (split, judging, distance=None) |
| gamma_phi_units._admissibility | (split, state, provider, context, tolerances, note) | `_split_admissibility(split, judging)` (renamed: SYN's and PR's name for the concept) |
| gamma_phi_units._stability | (provider, flows, temperature, pressure, phase, context) | (flows, temperature, pressure, phase, judging) |
| gamma_phi_units.require_composition_dependent | new | (provider) -> None: today's guard, :390-394, same message literal |
| gamma_phi_units.admissibility_checks | new | (view, splits, declared, degenerate, judging): the tail :476-488, see 5.4 |
| gamma_phi_units.revision_checks | public | removed (c) |
| pr_c1.split_checks | (split, components, state, provider, context, tolerances, note) | (split, judging) |
| pr_c1.declared_port_checks | (view, state, provider, context, note, declared_ports) | (view, declared_ports, judging) |
| pr_c1._fresh_dew | (provider, context, stream, components, *, id, subject, note) | (stream, judging, *, id, subject) |
| pr_c1._closure | (*, id, subject, provider, context, vapor, liquid, components, tolerance, note) | (*, id, subject, vapor, liquid, judging); tolerance read as `judging.tolerances["temperature"]` |
| pr_c1._split_admissibility | new (b) | (split, carried, vapor, liquid, judging) |
| split_checks._split_checks | (split, components, state, provider, context, tolerances, note, distance=None, *, unresolved=False) | (split, judging, distance=None, *, unresolved=False) |
| split_checks._split_admissibility | (at, provider, context, tolerances, note) | (at, judging) |
| split_checks._declared_phase | (stream, phase, components, state, enthalpy, provider, context) | (stream, phase, enthalpy, judging) |
| split_checks._declared_port_checks | (view, state, enthalpy, provider, context, tolerances, note, degenerate) | a: (view, enthalpy, degenerate, judging); b: (view, declared_ports, enthalpy, degenerate, judging) |
| table._Judging | NamedTuple | removed |
| table._stream_enthalpies | (view, at, routing, provider, context) | (view, routing, judging) |
| table._instance_rows | (view, state, enthalpy, degenerate, judging) | (view, state, enthalpy, degenerate, reaction_note, judging) |
| table._mixture/_pr/_syn_admissibility | (..., judging) | unchanged signatures; field reads instead of the positional unpack |
| table._declared_ports | new (b) | () -> dict: `{model: entry.declared_ports for model, entry in MODEL_CHECKS.items()}` (today's :412) |
| table._routing | new (c) | (form, view, splits, owners, judging) -> _Routing |

Bodies change only by the substitution of a parameter by its `judging.<field>` (an AST comparison per function,
quoted in each step's commit message, finds no other difference), except the items of 5.3-5.5. Placement (playbook
rule 5 for new code; existing functions keep their places): `require_composition_dependent` then
`admissibility_checks` at the end of gamma_phi_units.py (where `revision_checks` is today); `_declared_ports` after
`_syn_admissibility`, its last sibling caller; `_routing` directly after `revision_checks`; PR's
`_split_admissibility` directly after `split_checks`.

### 5.3 The kit's shared rows (step b; table_kit.py, after `ModelChecks`, under a header
`# -- the split family's rows (K04 §4.7; T05b spec §9.1) --`, in this order)

- `degenerate_split_rows(name, subject, distance, tolerances, note) -> list[CheckResult]`: split_checks.py:143-167
  moved verbatim, renamed. SYN calls it with `judging.tolerances, judging.note`; γ–φ's `split_checks` replaces its
  inline pair (gamma_phi_units.py:310-327, identical rows) by a call with `judging.tolerances, judging.note + BAND_NOTE`.
- `independent_split_rows(name, subject, total, differences, judging) -> list[CheckResult]`: `evaluated` of
  `independent_split.<name>.total` with `value=total`, then for `component, difference in zip(judging.components,
  differences, strict=True)` one `independent_split.<name>.<component>` with `value=difference`; every row
  `category="independent_split"`, `subject=subject`, `tolerance=judging.tolerances["molar_flow"]`,
  `reference=KIND_REFERENCE["molar_flow"]`, `independence_qualification=judging.note` (today's keywords exactly). The
  caller computes, in this order: `total = state[split.vapor_total] - sum(<fresh vapour>.n)`, then `differences` by a
  loop over `range(len(judging.components))` with today's per-component expression:
  SYN and PR `vapor[index] - flashed.vapor.n[index]`; γ–φ `by_vapor = vapor[index] - fresh_vapor.n[index]`,
  `by_liquid = liquid[index] - fresh_liquid.n[index]`, `by_vapor if abs(by_vapor) >= abs(by_liquid) else by_liquid`.
  Then `checks += independent_split_rows(...)`.
- `DeclaredStream` (split_checks.py:293-301 moved, renamed) and `declared_streams(view, declared_ports)`
  (split_checks.py:304-322 moved, renamed, one change: `ports = declared_ports.get(instance.model_id)`;
  `if ports is None: continue`; `for port, several in ports:` instead of the `MODEL_CHECKS` entry). Docstring:
  `declared_ports` maps a model id to its entry's `(port, several)` pairs; the iteration order and ids are today's.
  SYN's `_declared_port_checks` and PR's `declared_port_checks` both iterate it; table passes `_declared_ports()` to
  both (`_pr_admissibility`, `_syn_admissibility`), so split_checks.py drops its `MODEL_CHECKS` import.
- PR `split_checks` (b): reads the state in today's order (vapour columns, liquid columns, T, P, then the feed into
  `carried`), then `checks = [_split_admissibility(split, carried, vapor, liquid, judging)]`, then the dormant-feed
  return, the flash and its refusal (:364-366 unchanged), then the rows above. `_split_admissibility` is today's
  ladder (:306-357) with `name`, `subject` recomputed from `split`, the totals `sum(vapor), sum(liquid)` computed at
  its top, `carried.temperature`/`carried.pressure` for the closure's states (the same objects StreamState stored),
  placed directly after `split_checks` (playbook rule 5).

### 5.4 The γ–φ form inside `table.revision_checks` (step c)

```text
revision_checks(view, splits, state, *, provider, context, tolerances, judged_at=None, owners=None):
    at; note; reacting; reaction_note            # today's four statements, unchanged
    form = forms.form_of(view.basis.provider_id)
    judging = Judging(state=at, components=view.components, provider=provider, context=context,
                      tolerances=tolerances, note=note)
    routing = _routing(form, view, splits, owners, judging)
    enthalpy, energy = _stream_enthalpies(view, routing, judging)
    stream_bounds; instance_rows (with reaction_note); material; energy (+= instance, envelope)   # unchanged
    if form == forms.GAMMA_PHI_UNITS:
        from openflowsheet.verify import gamma_phi_units  # noqa: PLC0415  (loaded by _routing in this call)
        admissibility = gamma_phi_units.admissibility_checks(
            view, splits, routing.declared, routing.degenerate, judging)
    elif form == forms.DECLARED_MIXTURE:
        admissibility = _mixture_admissibility(view, routing.declared, routing.saturated, judging)
    elif form == forms.PR:
        admissibility = _pr_admissibility(view, splits, judging)
    else:
        admissibility = _syn_admissibility(view, splits, enthalpy, routing.degenerate, judging)
    return [...]                                 # today's category-major list, unchanged

_routing(form, view, splits, owners, judging) -> _Routing:      # directly after revision_checks
    if form == forms.GAMMA_PHI_UNITS:
        from openflowsheet.verify import gamma_phi_units  # noqa: PLC0415
        gamma_phi_units.require_composition_dependent(judging.provider)
        declared = forms.declared_phases(view)
        degenerate = gamma_phi_units.degeneracy(view, splits, judging.state, judging.provider, judging.context)
        return _Routing(pr=False, mixture=True, declared=declared, saturated=frozenset(), degenerate=degenerate)
    pr = form == forms.PR
    mixture = form == forms.DECLARED_MIXTURE
    declared, saturated, degenerate: today's table.py:143-154 with judging.<field> for at/provider/context/tolerances
    return _Routing(pr=pr, mixture=mixture, declared=declared, saturated=saturated, degenerate=degenerate)

gamma_phi_units.admissibility_checks(view, splits, declared, degenerate, judging):
    admissibility = []
    for split in registry_splits(view, splits):
        admissibility += split_checks(split, judging, degenerate.splits.get(split.unit))
    admissibility += forms.stream_admissibility(view, declared, judging.state, judging.provider,
                                                judging.context, judging.note)
    return admissibility
```

The dispatch reads `form`, never `routing.mixture` (which is True for γ–φ): no rung-order trap. `_Routing.mixture`'s
comment becomes "the declared-phase mixture route (`verify.forms`): the DECLARED_MIXTURE form and the γ–φ form, whose
streams outside the registry splits are read as the first pass reads them (units design §4.8)". The revision_checks
docstring names the γ–φ form and `_routing`'s guard; the gamma_phi_units module docstring's first paragraph is
rewritten (the table runs the form; this module supplies the guard, the routing and the form's admissibility rows);
`__all__` loses `revision_checks` and its now unused imports go (`bounds_checks`, `qualification`,
`REACTING_MODELS`, `_envelope_energy`, `_envelope_material`, `REACTION_DATUM_NOTE`, `ModelChecks`, `Unit`,
`MODEL_CHECKS`; ruff decides the exact set). In step a, `gamma_phi_units.revision_checks` already calls
`require_composition_dependent(provider)` as its first statement and `admissibility_checks(...)` for its tail.

### 5.5 Evaluation-order ledger (each item: why it is bitwise identical)

1. (a) `Judging(...)` is built before the degeneracy ladder (`_Judging` was built after `_stream_enthalpies`):
   a frozen dataclass from locals, which calls nothing and cannot raise.
2. (b) PR: `sum(vapor)`, `sum(liquid)` run inside `_split_admissibility`, after `carried` is built: the same sums of
   the same tuples; building `carried` reads the state and constructs a dataclass, and if it raises (KeyError) the
   sums had no observable effect today. State reads keep today's order.
3. (b) All forms: per-component differences are computed before the rows instead of between `evaluated` calls:
   `evaluated` (verify/__init__.py:160-184) is pure; `.total` is still computed first and the components in order;
   an IndexError at component k is raised before any row is returned, as today.
4. (b) γ–φ degenerate pair: `judging.note + BAND_NOTE` is concatenated before the call instead of in the keyword:
   the same string.
5. (c) γ–φ: the removed entry's own prelude made two `provider.describe()` calls (`qualification` and
   `reaction_note`) whose values table.revision_checks had already computed from the same provider; they are gone.
   Everything else runs in today's order: guard (its own `describe`) -> `declared_phases` -> γ–φ `degeneracy` ->
   enthalpy map -> stream bounds -> instance rows -> envelope material -> envelope energy -> registry split rows ->
   stream admissibility -> own admissibility. `pure_fluid_provider` is not called on the γ–φ path, as today.
6. (c) `bounds_checks` before the units list (γ–φ built the list first): `Unit` construction calls nothing (the same
   hoist R-W3-G5-12 accepted for table.py).
7. (c) The lazy import first executes in `_routing`'s γ–φ rung, at the point today's import executes (right after
   form resolution); the second statement finds the module loaded and binds a name only.

## 6. Work orders (commit order)

Each step: lane worktree from the `wp/S19` tip; plan commit, then step commit; enqueue `--mode interface --plan
.codehealth/interface/<id>.toml --snapshot`; one summary line. Before enqueueing, a static trial of the gate's static
checks at the step's base (as i12d-1 did) fixes the plan's literal entries; they are copied from the trial output,
never written by hand. Each commit message quotes: the AST-comparison sentence, patch_noop's summary line, the arch
line, the scan numbers of the touched files, and gate G3's counts.

- **WO-1, T1, test commit outside gate** (orchestrator-reviewed). tests/test_m02_wo8_verifier.py: :42 becomes
  `from openflowsheet.verify import pr_c1, table_kit`; add after the module constants (:51-54)
  `def _judging(state: Mapping[str, float]) -> table_kit.Judging:` returning `table_kit.Judging(state=state,
  components=COMPONENTS, provider=PROVIDER, context=CONTEXT, tolerances=TOLERANCES, note=NOTE)` (uncalled until a;
  the file has `from __future__ import annotations`, and mypy covers src and benchmarks only). Accept: the file's
  pass/skip counts equal the base's; ruff check and format clean.
- **WO-2, step a `i20a-judging`.** 5.1, 5.2 rows marked a, and in table.py the field reads; the three test statements
  (:171, :230, :238) rewritten in place to `pr_c1.split_checks(split, _judging(state))` and
  `pr_c1.declared_port_checks(view, ports, _judging(state))` / `(view, liquid, _judging(state))`. Accept: gate PASS;
  G3 with no difference; G5; G6.
- **WO-3, step b `i20b-split-rows`.** 5.3. Accept: gate PASS; G3 with no difference; pr_c1.py health >= 9.0 here
  (its last step); G8 falsifier on table_kit.py.
- **WO-4, R, retarget outside gate before c** (orchestrator-reviewed, test-only). tests/test_s11_gp_verifier.py:
  :293, :359, :493 `gamma_phi_units.revision_checks(` -> `table.revision_checks(`; :378 -> `original(` (inside `both`,
  which is installed on `table.revision_checks`); module docstring :3-4 says the tests go through
  `table.revision_checks`. tests/s11_gp_support.py: :278 and :286 point at `admissibility_checks`; docstrings :7-10
  and :276-277 say it counts the γ–φ form's admissibility rows of each check set. Accept: both GP files pass at R's
  head with the base's counts (each retargeted call is the dispatcher forwarding the same arguments: table.py:131-142,
  basis `wilson-ig-v2`, revision_flowsheet.py:138, :155); spy liveness (a raising fake makes the five
  `gamma_phi`-fixture tests of test_s11_gp_solve.py fail; quoted); patch_noop 0, total unchanged.
- **WO-5, step c `i20c-merge`.** 5.4. Accept: gate PASS; G3 with exactly the 5.5 item 5 difference; G7 numbers;
  `grep -rn "gamma_phi_units.revision_checks\|revision_checks.*gamma_phi" src tests scripts benchmarks examples`
  empty; the spy's liveness rerun at c's head.
- **WO-6, review and close.** One `reviewer` pass over WO-1 to WO-5 against this note (tier S2 cadence: 3 gated
  steps), then the lane merge into `wp/S19` with its full-suite run; `codehealth docs` reports no new broken
  reference (no living doc names a moved name at 356ee519); card `executed`.

Order rationale: the merge goes last, so a failure of R's fact check (risk F2) blocks only c, and a and b stand alone.

## 7. Interface plans

Common keys: `approved_by = "Frank Peters, 2026-11-19, Decision Desk ofs-s19-verify-twins choice A (ADR 0076 addendum
I-20)"`; `renamed = {}`; `new_files = []`; `reason` names this note, lists the moves of 5.2/5.3/5.4, says "no string
literal is added; literals dropped only by consolidation" (or the trial's entries) and carries the arch numbers
measured on the step applied at its base.

| id | removed | changed | added | callers |
|---|---|---|---|---|
| `i20a-judging` | [] | gamma_phi_units.py:split_checks, pr_c1.py:split_checks, pr_c1.py:declared_port_checks | table_kit.py:Judging, gamma_phi_units.py:admissibility_checks, gamma_phi_units.py:require_composition_dependent | tests/test_m02_wo8_verifier.py |
| `i20b-split-rows` | [] | [] | table_kit.py:DeclaredStream, table_kit.py:declared_streams, table_kit.py:degenerate_split_rows, table_kit.py:independent_split_rows | [] |
| `i20c-merge` | gamma_phi_units.py:revision_checks | [] | [] | [] |

(Paths in full as `src/openflowsheet/verify/<file>`. table_kit.py has no `__all__`; the two others gain or lose the
listed names in theirs, kept sorted.)

## 8. Verification gates

- **G1 tests:** the gate's tests tier PASS at every step; plus, run explicitly at each step's base and head, the
  verifier set: the files naming `revision_checks`, `split_checks`, `declared_port_checks`, `gamma_phi_units` or
  `count_gamma_phi` (11 test files at 356ee519: test_m02_wo8_verifier, test_s11_gp_solve, test_s11_gp_verifier,
  test_s11_verifier_forms, test_s19_component_order, test_st_core, test_t05b_verifier, test_t05b_zero_flow,
  test_t05_table_independence, test_t05_w12_table, test_t05_w1d_verifier) plus test_m02_wo8_g7 and
  test_m02_wo9_reactor: passed, skipped, xfailed counts equal at base and head.
- **G2 identity:** `scripts/corpus_identity.py --check` identical (F0) and `registry_builtin.py --check` clean at
  every step; MCP digest tier green.
- **G3 recorded-call equivalence** (uncommitted pytest plugin in the engineer's scratch, `-p rce -p no:xdist`,
  `PYTHONHASHSEED=0`, over G1's set). It wraps the module attributes `table.revision_checks`, `pr_c1.split_checks`,
  `pr_c1.declared_port_checks`, `gamma_phi_units.split_checks` (and, where they exist, `revision_checks` and
  `admissibility_checks` of gamma_phi_units), recording per call the test node id, the name and the result as tuples
  (id, category, subject, result, `float.hex` of value and tolerance, reference, near_threshold, reason,
  independence_qualification); and the class methods `flash`, `evaluate_phase`, `stability`, `describe` of every
  provider class in `verify.certificate.FRESH_PROVIDERS` plus `PrC1Provider`, `Syn001Provider`,
  `WilsonIdealGasProviderV2`, recording node id, method and `repr` of the request. Pass: for every function present
  at both base and head, the per-node result sequences are equal; the provider sequences are equal at a and b; at c
  they are equal after deleting every `describe` record, and `describe(base) - describe(head)` equals exactly 2 x the
  number of `table.revision_checks` calls on a `wilson-ig-v2` view. Quote N calls, N provider records, N describe at
  base and head.
- **G4 arch:** `codehealth arch --depth 4` 0 violations, 0 cycles at every commit; files 329 throughout; imports as
  the plan states (measured on the step applied at its base; a mismatch stops the step). Expected direction: a +1
  (`pr_c1 -> table_kit`), b -1 (`split_checks -> unit_checks` gone), c down (gamma_phi_units loses
  `flowsheet_rows` and `unit_checks`).
- **G5 interface:** public_api equals the plan exactly; callers rule; literals per the trial.
- **G6 patches:** `patch_noop.py .` 0 flagged after every commit, total not lower than the base's.
- **G7 health** (`codehealth scan` at c's head; predicted from report.py's penalties):

  | file | base | predicted | floor |
  |---|---|---|---|
  | gamma_phi_units.py | 6.4 / debt 19.0 | 9.3 / 3.0 (degeneracy complex 0.5, `_phase_flow` many_args 0.2) | 9.0 |
  | pr_c1.py | 7.7 / 23.4 | 9.6 / 2.0 (`band`, `_phase_property` many_args) | 9.0 |
  | table.py | 8.8 / 3.0 | 9.6 / 4.0 (revision_checks 8, `_instance_rows` 6 params) | 8.8 |
  | split_checks.py | 8.7 / 16.2 | 9.2 / 7.0 (four routing-phase functions' params) | 8.7 |
  | table_kit.py | 10.0 / 0 | 10.0 / 0 | 10.0 |

  Repo debt predicted 3439.5 -> about 3394. A miss of a floor is reported with the remaining smells, never chased by
  fragmenting (S19_RULES rejected list).
- **G8 R-016:** tests/test_t05_table_independence.py and test_m02_wo8_verifier's R-016 test pass; falsifier at b's
  head: appending `from openflowsheet.orchestrator.region import _kernel` inside a function of table_kit.py makes
  test_t05_table_independence fail (quoted, then reverted); forbid rule 0 violations.
- **G9 static:** `mypy` (src, benchmarks) and `ruff check`/`ruff format --check` clean.

## 9. Risks and open questions (each with a default)

- **F1 (fact, found here):** S11.A73's two tests compare the γ–φ form with itself. The "wilson" routing case and the
  column cases use `WILSON_RECORDS` (tests/test_s11_routing.py:128-130), whose basis is `wilson-ig-v2`
  (revision_flowsheet.py:138, :155), so `table.revision_checks` already dispatches them to
  `gamma_phi_units.revision_checks`; after R both sides are textually `table.revision_checks`. **Default:** retarget as
  WO-4 says (call sites only; a retarget never changes a test case), record F1 in S19_DECISIONS, and file for after
  S19 a test item restoring the cross-form comparison with `monkeypatch.setitem(forms._FORMS, "wilson-ig-v2",
  forms.DECLARED_MIXTURE)` on one side (the mechanism tests/test_s19_component_order.py:48 already uses).
- **F2 (fact):** every γ–φ check set of the five `gamma_phi`-fixture tests yields at least one admissibility row
  (registry split rows plus stream rows), so the retargeted spy's `count > 0` holds. Measured by WO-4's acceptance.
  **Default:** if a count is 0, WO-4 stops before any src change of c; steps a and b stand; the orchestrator picks
  the spy's target.
- **F3 (fact):** no test observes `describe()` call counts on the γ–φ verify path. Measured by G1 and G3 at c.
  **Default:** accept the two dropped calls as identical behaviour when G3 shows only them; if a test fails on a
  count, stop c and report.
- **F4 (fact):** the literal check accepts the consolidations of b and the deletion of c (`_literal_reach` follows
  bare names across touched files, gate.py:267-274). **Default:** the static trial decides; refused literals go into
  `literals_removed` with the reason "consolidated into table_kit.<function>".
- **P1 (Frank, preference):** the new public names `Judging`, `admissibility_checks`, `require_composition_dependent`,
  `DeclaredStream`, `declared_streams`, `degenerate_split_rows`, `independent_split_rows`. **Default:** as written;
  renames are free until step a lands, an interface step after.
- **P2 (orchestrator, scope):** SYN's private split functions adopt `Judging` (no public change). **Default:** yes,
  they are the third sibling and the source of the shared rows.
- **P3 (orchestrator, scope):** the out-of-scope functions of section 1 keep their signatures. **Default:** a later
  code-health item may move them onto `Judging`; not in S19.
- **R1 (risk):** step a touches five src files and one test. Mitigation: field-substitution only, AST comparison per
  function, G3. If an engineer nears 150k context, the step stops at a gated commit and a fresh engineer continues.
- **R2 (risk):** PR's declared-port and closure values now read `judging.components`, which in the test is
  `thermo.pr_c1.COMPONENTS` where `view.components` was read. Equal tuples there (C1 basis); test_m02_wo8_verifier
  pins the dew value (0.9e-8 < v < 1.1e-8), so a mismatch fails loudly at a.
