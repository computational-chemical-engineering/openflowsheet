# Binding-package recon (read-only; facts only; 2026-10-26, main @ 8c34ecb0)

Anchors are `path:line` in /home/frankp/Codes/OpenFlowsheet. Nothing was built or run.
No document, plan WO or ADR is named "binding package": `grep -i binding docs/implementation-plan.md`
hits only "bindings" in table rows. The phrase lives in S05/S07/S10/S10-C/L01 prose and R-535/R-616/R-709/R-781.

## 1. SELECTABLE_BASES

- `src/openflowsheet/application/revision_binding.py:1522-1540`: `class _SelectableBases(Sequence[ComponentBasis])`
  delegates `__getitem__`/`__len__` to `selectable_bases()` on every access (no state, R-219, T07 G20).
  `SELECTABLE_BASES: Final[Sequence[ComponentBasis]] = _SelectableBases()` at :1540.
- `src/openflowsheet/models/revision_flowsheet.py:135-139`:
  ```
  def selectable_bases() -> tuple[ComponentBasis, ...]:
      return (SYN001_BASIS, _c1_basis())
  ```
  Only two bases exist: SYN-001 and `pr-c1-v1`. Nothing else is selectable.
- Shape: `ComponentBasis` frozen dataclass, `revision_flowsheet.py:96-111`: `provider_id: str`,
  `components: tuple[str,...]`, `molecular_weights: Mapping[str,float]`.
  `SYN001_BASIS` :115 (`ComponentBasis(SYN001_PROVIDER_ID, ("A","B","C"), MOLECULAR_WEIGHTS)`).
  `_c1_basis()` :118-126 calls `pr_c1.load_records()` (records read on first use).
- Selection: `revision_flowsheet.py:129-132`:
  ```
  def component_basis(document):
      source = (document.get("component_set") or {}).get("record_source")
      return _c1_basis() if source == pr_c1.RECORDS_PATH else SYN001_BASIS
  ```
  i.e. a revision selects a basis by string equality of `component_set.record_source` with
  `pr_c1.RECORDS_PATH` (= `benchmarks/m01/components.yaml`, `thermo/pr_c1.py:67`). No basis key field exists;
  there is no record-less selector. `_read` (`revision_flowsheet.py:338`) stores it as `RevisionView.basis` (:255-256).
- Readers of `SELECTABLE_BASES` (code):
  - `application/revision_binding.py:1531,1534` (own delegation)
  - `benchmarks/m06/w27/snapshot.py:175` (basis loop, route rows), `:211` (`bases-v1` iff attribute exists)
  - `benchmarks/l01/retake.py:93` (measurement-only monkeypatch appends `pr-lib-v1`; not in the build)
  - `scripts/t08_support_matrix.py:157,170` (providers axis = provider ids)
  - Text-only mentions in `scripts/s04_evidence_manifest.py:188`, `s05_evidence_manifest.py:89`,
    `s07_evidence_manifest.py:146`, `s10c_evidence_manifest.py:587`.
- Readers of `component_basis` (basis choice): `application/validation.py:285` (`.molecular_weights`),
  `verify/certificate.py:665` (`.provider_id`), `revision_flowsheet.py:338`.
- Schema: `schemas/process-revision.schema.json:33-41`: `component_set` requires `record_source` (string,
  minLength 1, "Path to the file holding the referenced ComponentRecords") and `components`.
  Frozen-schema list: `docs/interfaces-frozen.md` §2 (plan §2.2). Any schema change needs an ADR.
  Frozen Protocol signatures: `docs/interfaces-frozen.md` §1.

## 2. MODEL_BUILDERS and MODEL_BASES (admission)

- `revision_binding.py:1476-1497` `MODEL_BUILDERS: Final[Mapping[str, Builder]]`, 22 keys:
  13 `syn001.*` (`feed_source, adiabatic_mixer, tp_heater, tp_flash, stream_splitter, product_sink, ph_flash,
  valve, liquid_pump, conversion_reactor, component_separator, heat_exchanger, kinetic_cstr`) and 9 `c1.*`
  (`feed_source, adiabatic_mixer, tp_heater, tp_flash, stream_splitter, product_sink, reactor, reactor_standin,
  reactor_surrogate`). Comment at :1472-1475 says the M04 surrogate's builder refuses; binder uses
  `_c1_reactor_surrogate_of` instead.
- `revision_binding.py:1461-1464` `MODEL_BASES: Final[Mapping[str, frozenset[str]]]`:
  ```
  **{s.model_id: frozenset({SYN001_PROVIDER_ID}) for s in _SYN001_SIGNATURES},
  **{s.model_id: frozenset({C1_PROVIDER_ID}) for s in _C1_SIGNATURES},
  ```
  Comment :1455-1460: "each `syn001.*` model on SYN-001's basis only, each `c1.*` model on the C1 basis only" (R-288).
  `_SYN001_SIGNATURES` :1419, `_C1_SIGNATURES` :1438, `MODEL_SIGNATURES` :1452.
- Admission in the binder, `revision_binding.py:1651-1655`:
  ```
  if instance.model_id not in MODEL_BASES:
      return Unbound("unsupported", f"model_unsupported({instance.model_id})")
  if view.basis.provider_id not in MODEL_BASES[instance.model_id]:
      return _basis_refusal(instance.model_id, view.basis)
  ```
  `_basis_refusal` :1543-1551 builds the hint naming the bases and the same-function namesake (`_NAMESAKES` :1505).
- Provider per basis: `revision_binding.py:1608-1617` `basis_provider(basis)`: `pr-c1-v1` -> `PrC1Provider()`;
  `basis == SYN001_BASIS` -> `Syn001Provider()`; else `ValueError("no provider for basis ...")`.
  Called at :1670 `provider = PropertyMeter(basis_provider(view.basis))`; builder at :1674
  `builder = MODEL_BUILDERS[instance.model_id]`, called :1676-1678 with `(replace(instance, pins=reader), provider, _CONTEXT, view.components)`.
- Second provider table: `verify/certificate.py:615-628` `fresh_provider(provider_id)` (only `syn001` and `pr-c1-v1`;
  else `VerifierError("provider_unknown(...)")`); `:704` `basis_mismatch` check.
- Identity guards that refuse non-C1 providers: `models/c1/units.py:50-58` (`c1_provider`), `models/c1/blocks.py:128-136`.
  No equivalent guard found in `models/syn001/` (grep for `!= PROVIDER_ID` / `provider_id !=` found none there).
- Other readers of MODEL_BUILDERS: `application/local.py:1098-1103` (`list_models`: every builder, no basis filter),
  `application/replacement.py:303` (`resolvable`), `models/revision_flowsheet.py:19` (docstring only).
- Column and cascade: not in `MODEL_BUILDERS`. Model ids `syn001.column` (`models/syn001/column.py:128`) and
  `syn001.cascade` (`models/syn001/cascade.py:87`). Module-level symbols are specs and id helpers
  (`ColumnSpec` :396, `CascadeSpec` :279); `grep "^def build\|^def make"` found no builder in either file.
  Binder refuses them `model_unsupported` (U04: `benchmarks/t08/support_envelope.yaml:345-350`).
  R-535 (`docs/decision-register.md:10869-10880`) and `docs/S02_DECISIONS.md:17` keep S02 column library-only.
- Gamma–phi: `models/syn001/gamma_phi.py`, `gamma_phi_blocks.py`, `equilibrium_form.py`. `equilibrium_form.py:59`
  `ADMITTED: Mapping[tuple[str,str], str]` keyed on `(provider_id, reference_convention)`; `:88` looks up
  `ADMITTED.get((capabilities.provider_id, capabilities.reference_convention))`. Not in MODEL_BUILDERS.

## 3. Property-provider interface and the bases' APIs

- Protocol: `src/openflowsheet/thermo/__init__.py:209-224` `@runtime_checkable class PropertyProvider(Protocol)`:
  `describe(self) -> PropertyCapabilities`; `evaluate_phase(self, request: PropertyRequest, context: EvaluationContext) -> PropertyResult`;
  `flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult`. Frozen (`docs/interfaces-frozen.md` §1).
  No saturation, entropy, volume or fugacity method on the protocol: those are property ids
  (`PropertyRequest.properties`, :133-146, with `derivatives` :146).
- `PropertyCapabilities` `thermo/__init__.py:62-103`: provider_id, implementation_sha256, data_sha256,
  reference_convention, state_definition, components, phases, properties, flashes, derivative_order, domain,
  uncertainty, data_provenance, thread_safety, numerical_limitations (all required).
- Flowsheet path: `orchestrator/budget.py:83` `PropertyMeter(provider)` wraps it (counts calls; regions capture it at
  declaration). Units reach it through `compile/spec.py:67` `PropertyBlock` and `models/syn001/blocks.py`,
  `models/c1/blocks.py`.

Per provider (the basis-facing class, declared properties and flashes, from `describe()`):

| provider id | class (file:line) | properties declared | phases | flashes | components |
|---|---|---|---|---|---|
| syn001 | `Syn001Provider` `thermo/syn001.py:74` | `h`, `lnK` (:90) | LIQUID, VAPOR | TP | A,B,C (`syn001.py:51`) |
| pr-c1-v1 | `PrC1Provider` `thermo/pr_c1.py:711` | `h`,`Z`,`v`,`lnphi_<c>` (`PROPERTIES` :226) | LIQUID, VAPOR | TP | H2,N2,NH3,Ar,CH4 (:70) |
| iapws95-v1 (S05, library-only) | `Iapws95Provider` `thermo/iapws95.py:806` | `h,s,v,Z,cp,lnphi_H2O` + `Psat,Tsat` (:128-130) | LIQUID, VAPOR | TP | H2O (:77) |
| coolprop-heos-v1 (S07, library-only) | `CoolPropHeosProvider(component_id)` `thermo/coolprop_heos.py:390,398` | `h,s,v,Z,cp,lnphi_<comp>` (:434) + `Psat,Tsat` (:109) | LIQUID, VAPOR | TP | one fluid per instance, `components=(fluid.component,)` (:927) |
| wilson-ig-v1 (S10, library-only) | `WilsonIdealGasProvider(records_path=None)` `thermo/wilson_ig.py:433,441` | `h`, `lnphi_<c>` only (:446) | LIQUID, VAPOR | TP | from `benchmarks/s10/records.yaml` (:81) |
| pr-lib-v1 (S04, library-only) | `PrLibProvider` `thermo/pr_lib.py:686` | `h,Z,v,lnphi_<c>` (:243) | VAPOR only (:701) | none (:703) | 9 records, `benchmarks/l01/components.yaml` (:75) |

- Extra public methods not on the protocol: `wilson_ig.py:705` `stability(state, phase, context) -> StabilityReport`;
  `coolprop_heos.py:414-430` classmethods `admitted()` / `excluded()`; `iapws95.py:243` `PhiJet`.
- Gaps against the flowsheet-facing set (h, s, v, phi, derivatives, saturation), facts only: Wilson exposes no
  `s`, `v`, `Z`, `cp` and no `Psat`/`Tsat`; pr-lib exposes no `s`, no saturation and no flash;
  syn001 exposes no `s`, `v` or `lnphi`. Derivative orders: syn001 `{T:1,P:1}` (`syn001.py:95`); Wilson `dict.fromkeys(("T","P",n_*),1)`.
- Activity models: the only γ–φ basis is Wilson (`wilson-ig-v1`, ideal-gas vapour; `wilson_ig.py:1`, S10 spec §3–§5, ADR 0047).
  `grep -rl "NRTL\|UNIQUAC" src` returns zero files. NRTL/UNIQUAC are named only in
  `docs/derivations/S10-spec.md:726-740, 1035, 1055` (IDAES/DWSIM references, LLE follow-on).
- Validators: `grep` for `basis_provider`, `fresh_provider` shows the only two dispatch tables (above), so a new basis
  needs an entry in each plus `PROVIDER_LINES` (W27, below).

## 4. Support matrix and envelope

- Script: `scripts/t08_support_matrix.py`. Header :1-30 (T08.A20 axes, A21 harvest, A22 unsupported rows, A23 byte render).
  `ENVELOPE` :55 = `benchmarks/t08/support_envelope.yaml`. `_scanned_providers()` :119 (module scan for `PROVIDER_ID`);
  `code_facts()` :152-184 (reads `MODEL_BUILDERS`, `SELECTABLE_BASES`, scans providers); `_axis` :185; `check_a20` :222;
  `check_a21` :532; `check_a22` :333; `check_a23` :594 (render compare); `render` :354; `main` :618.
  Usage (script's own docstring): `PYTHONPATH=src .venv/bin/python scripts/t08_support_matrix.py --check` (or `--emit`).
- Envelope file: `benchmarks/t08/support_envelope.yaml` (7184 lines). Sections: `axes:` :29 (property_model :30,
  components :56, domain :72, unit_models :82, topologies :127, specifications :144, solve_policies :179,
  globalization_and_recovery :194, verification :210, reproducibility :223, interfaces :236, platforms :274,
  external_execution :287); `unsupported:` :311 (U01–U15, each `id`, `capability`, `outcome`, `evidence`);
  `limitations:` :468 (L01–L42 and `L-CSTR-*`, `L-WS-*`; each `id`, `text`, `evidence`); `harvest:` :918.
- Providers axis: `property_model` at :30-55: `providers: [pr-c1-v1, syn001]` at :37 plus `other_basis_providers`
  (pr-c1-v1 with `limitation: L42`). L42 at :792-800.
- Unit-models axis: `unit_models` at :82; `members:` at :92 lists 22 names (`c1.*` and `syn001.*`), ending before
  `synthetic_members: [c1.reactor_standin]` at :116. Evidence for that axis cites `tests/test_m02_join.py::test_the_registry_holds_the_twenty_one_models_each_on_its_own_basis`.
- Library-only registry: `tests/test_t08_w2_support_envelope.py:335-342` `LIBRARY_ONLY_PROVIDERS = {"pr-lib-v1": "S04", "iapws95-v1": "S05", "coolprop-heos-v1": "S07", "wilson-ig-v1": "S10"}`.
  Its comment (:335-337): the commit that makes one selectable removes it, adds it to the providers axis, reclassifies its package's U02 items.
  `library_only_provider_problems` :345; C3 test :389-393 and controls :406.
- Harvest U02/U04 items: the `harvest:` list (:918-) classifies each item as E/S/P/B and cites `to` (e.g. `U02`, `U04`).
  S01 cascade items carry notes "`syn001.cascade` is library-only, not in MODEL_BUILDERS (U04)" at `support_envelope.yaml:3644-3683`.
  No `limitations` L-row for `syn001.column` or `syn001.cascade` was found; the grep hits I inspected are harvest notes.
  `grep -c S02` = 60 and `grep -c S06` = 54 in the envelope: I did not classify these; they are mostly harvest items citing S02/S06 manifests.
- Rendering: `docs/support-matrix.md` (byte-compared by T08.A23; test `test_t08_w2_support_envelope.py:168`).
- HARVEST_SIZE: `tests/test_m07a_harvest.py:56` `HARVEST_SIZE = (59, 832, 101)` = (files, limitations, checks).
  Assertion `:154-157` (`test_m07a_a50_the_harvest_size_is_the_quoted_one`): `found == HARVEST_SIZE` and
  `len(matrix.load()["harvest"]) == sum(HARVEST_SIZE[1:])`. Comment :40-51 lists per-package moves
  (S10 `wp/S10`, S08 `wp/S08`, S09, S10C, S08b). `scripts/s05_evidence_manifest.py:405-455` AST-reads and rewrites
  `HARVEST_SIZE` when a manifest is appended ("HARVEST_SIZE old -> new").

## 5. W27 "v2 mapping"

- "W27" = the OpenIDAES-450 benchmark registration, code in `benchmarks/m06/w27/` (`snapshot.py`, `registration.py`,
  `coverage.py`), data in `benchmarks/m06/openidaes450/`. v1 files are frozen.
- "W27 v2" = registration version 2 (R-570, `docs/decision-register.md:11717-11730`). Normative: `docs/derivations/W27-registration-v2.md`
  (W27v2-R01…R09). Data: `benchmarks/m06/openidaes450/registration_v2.json` (`tables.provider_methods`, `tables.provider_lines_added`,
  `tables.case_distinct`, `snapshots` S1…S3). Generator: `docs/derivations/scripts/w27_registration_v2.py`.
  Selected by explicit `registration_version`; `coverage.py:24-33`; `registration.py:23-25,50-52,83-90` (`provider_methods(version=1|2)`).
- v2 provider table (`W27-registration-v2.md` §4, W27v2-R02; `registration_v2.json`): `pr-c1-v1 -> cubic_pr`, `pr-lib-v1 -> cubic_pr` (only added row), `syn001 -> synthetic_syn001`.
  No row for `iapws95-v1`, `coolprop-heos-v1` or `wilson-ig-v1`.
- Snapshot side: `benchmarks/m06/w27/snapshot.py:149-156` `PROVIDER_LINES` has keys `syn001`, `pr-c1-v1`, `pr-lib-v1` only.
  `_pr_lib_line` :138-146 (records from `pr_lib.RECORDS_PATH`, phases `vapor`).
  `_routes_bases_v1` :158; the refusal for a provider without a line is at :184-189
  (`unsupported(provider ...: no registered records and phases, W27-R63)`).
  `reading_for` :209-217 returns `bases-v1` iff the binder has `SELECTABLE_BASES` and `MODEL_BASES`.
  `build_snapshot` :232.
- S05 F-3 (`docs/derivations/S05-IAPWS95-spec.md:474-475`, :859, :954): "Mapping W27's method string to `iapws95-v1` is a binding-package decision."
  W27 v1 `package_methods` in `benchmarks/m06/openidaes450/registration.json` (routes) names the IDAES method string `iapws95` (:2251, :2281); no route for `iapws95-v1`.
- What the docs say a new basis needs in W27: W27v2-R02 (provider method row), W27v2-R03 (a `PROVIDER_LINES`-style line:
  records path, phases from `describe().phases`; "A provider with no line here is still refused"), and the route rows of
  `registration_v2.json#/snapshots`. S05 spec §16 lists "F-3's W27 v2 mapping" as one of five parts of its Q-8.

## 6. Every entry that waits for the binding package (deferred, anchor, what)

1. `docs/decision-register.md:10869-10880` R-535: S02 stays library-only; column not in `MODEL_BUILDERS`; L-rows wait for "the binding package".
2. `docs/S02_DECISIONS.md:17`: S01/S02 L-rows for cascade/column left to the package that binds the column into `MODEL_BUILDERS`.
3. `docs/derivations/S06-spec.md:375-376` §15 Q7: flowsheet binding of `F`, `F_c`, `ν*`, `π*` (§14 at :340): "the binding package rules first".
4. `docs/derivations/S07-spec.md:167-172` §3.4 and `:528-532` §12.4: records-less pure-fluid basis package for `iapws95-v1` and `coolprop-heos-v1` (basis key, unit-model admission, W27 v2 mapping, support-matrix rows, envelope). "It needs its own ADR, because it changes `SELECTABLE_BASES`' shape."
5. `docs/derivations/S05-IAPWS95-spec.md:843-863` §16.4 "Binding: none" and `:950-960` Q-8 (five parts). Answered by Frank 2026-10-23: "Library only for now"; selectable-basis package planned later "together with S07". Default: no.
6. `docs/derivations/S05-IAPWS95-spec.md:369` A25 (library-only); `:474-475` F-3 (W27 mapping = binding-package decision).
7. `docs/adr/0046-s07-coolprop-pure-fluid-provider.md:159` D9 library-only; `docs/adr/0045-s05-iapws95-pure-water-provider.md:85`.
8. `docs/FRANK_QUESTIONS.md:169` Q-F2: "library only for now … flowsheet use with the binding package".
9. `docs/derivations/S10-spec.md:691` A27 (wilson absent from `SELECTABLE_BASES`); `:976` "Flowsheet admission (`SELECTABLE_BASES`): Frank's call"; `:1035`/`:1055` NRTL/LLE needs an interface ADR first.
10. `docs/derivations/S10C-design.md:66` (flowsheet admission: SELECTABLE_BASES, MODEL_BASES, Frank R-709/Q-F2); `:526` WO-5 keeps `LIBRARY_ONLY_PROVIDERS["wilson-ig-v1"]`; `:566` Q1: "No: library level only (R-709). A later package adds it with U02 reclassification".
11. `docs/decision-register.md:13749-13765` R-709: S10 library-only by default; "Admitting the provider to flowsheets now: Frank's scope call."
12. `docs/decision-register.md:15329-15337` R-781 and `docs/reviews/S10C-review.md:46-56` (F2): admission-time P1–P3 check deferred "to the package that makes the provider selectable in flowsheets (design Q1)"; register line 15337 "Affected packages: … the package that makes `wilson-ig-v1` selectable in flowsheets". Also `docs/derivations/S10C-spec.md:778-791`.
13. `docs/decision-register.md:11665-11700` R-568/R-569: library-only providers; R-569 (:11691): "its axis row and L-rows come with the selection".
14. `docs/decision-register.md:12548-12570` R-616 (S05 ships; library-only; line :12563 "No binding: `SELECTABLE_BASES`, `PROVIDER_LINES`, the support envelope's `property_model`, `LIBRARY_ONLY_PROVIDERS`").
15. `docs/briefs/S07-coolprop-design.md:22`: "binding package as a follow-on if not included".
16. `docs/V02_STATE.md:115`: "deferred to the binding package, R-781".
17. `docs/reviews/D1-rulings.md:58`: "R-535 already says S02's L-rows wait for the binding package."
18. Adjacent (L01, not the binding package by name): `docs/decision-register.md:12517-12520` R-615 (WO-L01-3b exposure waits for Frank's ship decision); `docs/derivations/L01-spec.md:602,625,637-662,701` (the `SELECTABLE_BASES` entry for `pr-lib-v1` is WO-L01-3's; identity statement; `:637` what the adding commit also does).
19. `docs/derivations/T08-release-spec.md:187,301,503`: the envelope's providers axis equals the providers of `SELECTABLE_BASES` (T08.A20); amended by S04 (R-568).

## 7. ADR and R numbering

- Highest ADR under `docs/adr/`: `0049-s10c-composition-dependent-k.md` (so next free: 0050). Recent: 0045 S05, 0046 S07, 0047 S10, 0048 S08, 0049 S10C.
  S07 §12.4 says the binding package "needs its own ADR" (not yet written; no file named for it).
- Highest R-number in `docs/decision-register.md`: R-794 (heading at :15619, "S08b: the identity gate…"). `grep -c "^## R-"` = 652 headings; numbering is not dense. Next free by max: R-795.

## 8. Existing tests that pin the current set of bases or builders

- `tests/test_m02_join.py:88-102`: `dict(MODEL_BASES) == REGISTERED` (:88-89 `set(MODEL_BASES) == set(MODEL_BUILDERS) == set(MODEL_SIGNATURES)`);
  `test_the_selectable_bases_are_what_component_basis_returns` :93-96 asserts `tuple(SELECTABLE_BASES) == (SYN001_BASIS, c1_basis)` and `len == 2`; :97-102 provider ids named.
- `tests/test_t08_w2_support_envelope.py:61-80`: `len(syn001 models) == 13`, `len(models) == 22`, `synthetic_models == ["c1.reactor_standin"]`,
  `providers == ["pr-c1-v1","syn001"]`, `scanned_providers == [coolprop-heos-v1, iapws95-v1, pr-c1-v1, pr-lib-v1, syn001, wilson-ig-v1]`,
  `len(operations) == 21`. Also :302-305 (`library_only_problems` vs MODEL_BUILDERS), :308-329 (controls), :337 LIBRARY_ONLY_PROVIDERS, :385-393 (C3), :168 (A23 byte render).
- `tests/test_t05_w1b_revision.py:84-…`: set of `syn001.*` builders = six K02 + six T05 + kinetic (13), literal.
- `tests/test_t08_kinetic_cstr.py:217-218`: `len(syn001) == 13`.
- `tests/test_t07_w5c_signatures.py:369,374`: `list(MODEL_SIGNATURES) == list(MODEL_BUILDERS)`; `set(_units_by_model()) == set(MODEL_BUILDERS)`.
- `tests/test_t07_w5a_inspection.py:132-134`: monkeypatches MODEL_BUILDERS; `list_models` equals sorted keys.
- `tests/test_t07_r6_hints.py:65-72`: every builder's pins and choices; `set(MODEL_SIGNATURES) == set(MODEL_BUILDERS)`.
- `tests/test_m02_wo8_units.py:61-73`: C1 builder set (`c1.` minus M04 models).
- `tests/test_m02_wo9_reactor.py:375, 505-514`: `c1.reactor_standin` in MODEL_BUILDERS; `MODEL_BASES["c1.reactor_standin"] == {pr-c1-v1}`.
- `tests/test_m02_wo8_region.py:266-272`, `tests/test_m02_wo11_promotion.py:324`, `tests/test_t05_w1c_executor.py:294-300`: monkeypatch MODEL_BUILDERS entries.
- `tests/test_t08_w1_typed_ends.py:61-89` (`models >= set(MODEL_BUILDERS)`), `tests/test_t08_w2_edge_identity.py:403-412` (`set(manifests) == set(MODEL_BUILDERS)`),
  `tests/test_t08_b50_surface_content.py:222` (uses `local.MODEL_BUILDERS`), `tests/m04_schema_support.py:20` (M04 model added to list_models).
- `tests/test_m06_w27_coverage.py:535-648, 577, 592, 607-648`: fake binder modules with `SELECTABLE_BASES`/`MODEL_BASES`; `bases-v1` reading fixtures.
- `tests/test_m02_wo7_binding.py:66-94`, `tests/test_t08_w2_unsupported.py:82-87`: `component_basis` on the C1 and l01 paths.
- `tests/test_l01_records.py:499-501`, `tests/test_l01_retake.py:154,166,174`, `tests/test_s05_envelope.py:216-221`,
  `tests/test_s07_registration.py:157-165`, `tests/test_s10_provider.py:688-696`: selectable set and `LIBRARY_ONLY_PROVIDERS` entries.
- `tests/test_m07a_harvest.py:56,154-157`: `HARVEST_SIZE`.
- Provider unit tests that construct the library-only classes (not pins on the set): `tests/test_s05_iapws95.py`, `test_s07_coolprop.py`,
  `test_s10_provider.py`, `test_s10_flash.py`, `test_s10c_*.py`.
- Run: `pyproject.toml:153-157` pytest config (`testpaths = ["tests"]`, `pythonpath = ["."]`). `scripts/gate.sh` runs `scripts/check.sh` with a log file and prints one summary line.
  Tests run as `.venv/bin/python -m pytest ...` (as the t08 script docstring shows `PYTHONPATH=src`). Not run in this recon.

## Not found

- A "binding package" work order, branch, ADR draft or plan row: none (implementation-plan.md has no such phrase; `docs/adr/` ends at 0049).
- Any record-less `ComponentBasis` selector: `component_basis` only matches `record_source` equality with `RECORDS_PATH`.
- NRTL or UNIQUAC code in `src/`: none (`grep -rl "NRTL\|UNIQUAC" src` = 0 files).
- A `MODEL_BUILDERS` entry or builder function for `syn001.column` or `syn001.cascade`.
- An L-row (limitations) for `syn001.column` / `syn001.cascade` / S02 / S06 in `benchmarks/t08/support_envelope.yaml`.
- W27 v2 rows for `iapws95-v1`, `coolprop-heos-v1`, `wilson-ig-v1`; `PROVIDER_LINES` has no entries for them.
- Saturation, entropy, volume, fugacity methods on the `PropertyProvider` protocol (only via property ids).
- Searched: `src/`, `tests/`, `scripts/`, `benchmarks/`, `schemas/`, `docs/` (incl. `derivations/`, `adr/`, `reviews/`, `briefs/`, `FRANK_QUESTIONS.md`, `decision-register.md`).
  Not searched in depth: `docs/design-history/` (archival, per CLAUDE.md), `evidence/` manifests beyond the `S05`/`S07` text hits.
- Not verified: CoolProp library install status on this machine; whether the `Syn001Provider` / `Iapws95Provider` constructors take arguments (only class lines were read).
