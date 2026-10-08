# M06 W27 registration — the OpenIDAES-450 external agent benchmark adaptation

**Status:** registered 2026-10-08, **before any W27 agent run**. Amended once, also before any run: §20
(Amendment 1, 2026-10-08: one erratum and three scoring rules, W27-R59…R61, from the M06 review F5). Design lane (`specifier`), M06 WO-15, branch
`wp/M06-w27`. Brief: `docs/briefs/M06-W27-registration.md` (`1fb65c1`).
**Machine-readable companion:** `benchmarks/m06/openidaes450/registration.json`, written by
`docs/derivations/scripts/m06_w27_registration.py` from the tables in that script and from
`benchmarks/m06/openidaes450/case_facts.json` (itself written by the same script from the pinned archive).
`python docs/derivations/scripts/m06_w27_registration.py --check` re-derives both and the dry illustration byte
for byte, and refuses when any self-claim of §14.1 fails.
**Not the campaign sample:** `benchmarks/m06/openidaes450/dry_illustration.json` (§15). The campaign sample is
drawn at M07 from the coverage of the v0.2 candidate by the procedure of §6.

---

## 0. Read this first

- A `verdict` agent judges W27 from **this document and the campaign record** (§13 lists what the record must
  hold). Nothing else is needed and nothing else is authority.
- Numbered items: **W27-R01…R61** are registration rules (R59…R61 by Amendment 1, §20); **GC-*** are the generator's self-claims (§14.1);
  **W27-A01…A40** are the assertions WO-16's tests and G15's dry run must pass (§14.2); **W27-S01…S18** are the
  registered scorer states (§14.3).
- Authority order for W27: blueprint §11.4 > plan v1.2 W27 row > design note `docs/design/M06-web-shell.md` §9
  > this registration, for everything §9 delegates to it (the maps, the classifier's rules, the sample, the
  prompt, the final answer, scoring, reporting). Where this document reads §9 more narrowly, §3 says so.
- The tables (which IDAES class does what, which name is which chemical, which property package is which
  method) are semantic judgements of the design lane. WO-16 implements them **as data**, read from
  `registration.json`; it does not re-decide them. A disagreement found while implementing is a finding for
  the design lane (an amendment to this document), never a local change.

## 1. Authority, scope, and what this registration establishes

**Authority.** The registration of W27 Tier 1 required by blueprint §11.4 ("adapted subsets must report coverage
and cannot inherit the original benchmark's headline score") and design note §9 Tier 1 ("Registration by the
`specifier` before any run (WO-15)"). Register entries R-176…R-179 (§19).

**Scope.** (a) The coverage classifier's rules — Tier 0 item 3 — which WO-16 implements and which are re-run
mechanically at M07 against the v0.2 candidate's registry. (b) The Tier 1 campaign: sample, agent
configuration, prompt, final answer, per-run scoring, reporting, claims. (c) The work orders for WO-16.

**What it establishes.** A complete, pre-registered procedure under which (i) every one of the 450 cases gets a
class with every applicable reason, from the case's own JSON and a registry snapshot, deterministically;
(ii) 45 cases are drawn by a seeded rule that nobody can steer after seeing the M07 coverage; (iii) each run
gets exactly one outcome class by a decision table, and the gated terms (system false verification,
unauthorized and critical effects) are counted by rules fixed now. It also establishes, as an illustration
only, what the rules give against today's registry (0.1.1) and against a hypothetical v0.2 snapshot.

**What it does not establish** — §16. In one line: no headline score, no comparison with CRAFTS, no numerical
agreement with IDAES, no claim that a `CANDIDATE` is representable beyond the necessary conditions §5 checks
and the confirmation of §7, and no claim about any model's agent ability beyond the 45 recorded runs.

## 2. Inputs (pinned)

| Input | Identity |
| --- | --- |
| Archive `OpenIDAES-450-demo.tar.gz` | 220 802 919 bytes, SHA-256 `6d42c02fdc7e8e4c81c861d77fd5b546198a2bfd7d9c87212c97149e50ea4526` (`provenance.json`; the audit's 220 433 394 bytes was an earlier upload, disclosed there) |
| `provenance.json` | SHA-256 `2198850dac2830338a1601ae9c99f5478d2d23e7033c456dadde0b678d480c74` (`e268ed8`) |
| `access_report.json` | SHA-256 `db4c4371db2128759f7cdaa4b602da0f78da958ba2ae26989bd4f6a08bd9dad7` (`e268ed8`): 450 rows; residual check 425/24/1; full82 = 82 (WaterTAP 41, IDAES 20, PrOMMiS 20, DISPATCHES 1) |
| `splits/full82.json` | SHA-256 `471a01d571b901a910f19881cca22c4b822f0da1513ee8d3b84f8f09f43b7c34`; its binding to the manuscript's score run is *not independently verified* (access report) |
| `case_facts.json`, `registration.json`, `dry_illustration.json` | SHA-256 printed by `--check`; recorded in the commit that carries this document and in `registration.json#/inputs` |
| Today's registry | `openflowsheet` 0.1.1; `list_models` canonical-JSON SHA-256 `4a60f5a3ad5def32a872407a75255370249560036e5718c848803637b2a5123a`; 13 models, all `syn001.*`; one property route, `syn001`, components A, B, C (`synthetic: true`) |

## 3. Findings that change other documents (stated here, not written there)

- **F1 — the agent model.** Design note §9 Tier 1 and §12 F2 name V17's `claude-sonnet-5`. Frank's answer to F2
  (2026-10-06) supersedes it: the most recent model at campaign time, pinned by exact id (§8). The design note
  needs that edit (session's), and the campaign is **not directly comparable with `v17-c2`**.
- **F2 — "the registry SHA-256".** Design note §9 item 3 and gate G14 record "the `list_models` document
  SHA-256". That document names models only: no component, no property route. The classifier needs both, so
  this registration defines a **registry snapshot** (§5.7) whose SHA-256 is recorded beside `list_models`'.
  G14's "registry SHA-256 recorded" should read "the `list_models` SHA-256 and the registry-snapshot SHA-256
  recorded".
- **F3 — what an agent can see.** At 0.1.1 no contract operation lists the available components or property
  routes; an agent learns them only from a refusal (`RevisionError("unsupported", "components_unsupported")`
  at validation). This is not a request to change the contract. The campaign measures agents under whatever
  surface v0.2 has, and the report states which (W27-R54).
- **F4 — one case cannot be prompted.** `watertap_metab` lacks six of the per-case files, `units.json` among
  them; it is `ARTIFACT_INCOMPLETE` and is outside the sampling frame (§6).
- **F6 — T08's U14 contradicts W27's file locations.** T08 release spec §5.3 row U14 ("external benchmark
  (CRAFTS/OpenIDAES-450) comparisons — not run in v0.1 (M06/W27)") is tested by
  `tests/test_t08_w2_unsupported.py::test_u14_no_external_benchmark_comparison_is_registered`, which fails on
  any tracked path under `src/` or `benchmarks/` containing `openidaes`. Design note §9 puts W27's records under
  `benchmarks/m06/openidaes450/`, so the test has failed since WO-14 (`e268ed8`, `provenance.json` and
  `access_report.json`), and `test_t08_w2_support_envelope.py::test_a22_…` fails with it. `benchmarks/` is not
  in the sdist (`MANIFEST.in`), so nothing ships. Recommended amendment (design lane, T08 spec; not made here):
  U14 reads "no external benchmark comparison is registered in `benchmarks/registry.yaml` or shipped in
  `src/`; W27's adaptation records (M06) live under `benchmarks/m06/openidaes450/` and register no comparison",
  and the node checks `registry.yaml` and `src/` only.
- **F5 — "agent false verification" for a built claim on a non-`CANDIDATE` case** (design note §9) is kept, but
  it is only as right as the maps. §11.6 adds the `map_defect_candidate` flag so that a build the maps called
  impossible but which passes every build check is shown to the verdict, not hidden; it does not re-score.

## 4. Case facts: what the classifier reads

**W27-R01 (sources).** The classifier reads, per case, only `case.json`, `specification.json`, `topology.json`,
`units.json`, `property_packages.json` and, for scoring, `streams.csv`; and from `access_report.json` the
row's `files_missing`, `parse_errors`, `residual_check` and `in_full82`. It **never** opens `sources/`, any
`.py`, `model.py`, `executable_source.py`, or a solver output, and never executes anything from the archive.
Where the case JSON does not identify something (most often a property package that only `sources/` defines),
the rule says what it is — `unidentified` — and does not guess (§5.6). Rationale: the archive is untrusted
data (blueprint §11.3), and a rule that reads source code is a rule nobody can re-run deterministically.

**W27-R02 (units).** If `units.json` is a non-empty list, the units are its entries (namespace `idaes:`), each
keyed `idaes:<normalise(class)>`, where `normalise` takes the class path's last segment and removes a leading
`_Scalar` or `_Indexed` and a trailing `Data` (`idaes.core.base.process_block._ScalarHeatExchangerNTU` →
`HeatExchangerNTU`; `…HelmTurbineStageData` → `HelmTurbineStage`). An entry whose name begins with another
entry's name followed by `.` or `[` is a **sub-block** of that unit (a flash's internal `split`, a column's
trays) and is not judged on its own. Otherwise the units are `topology.json#/units` (namespace `topology:`),
keyed `topology:<kind>`. Measured (GC-FACTS-4): 238 cases use `units.json` (the 237 `native_IDAES` cases and
one `original_reduced_model` case); the other 212 use the topology.

**W27-R03 (unit options).** The rules read eleven options of `units.json#/configuration`: `compressor`,
`dynamic`, `energy_mixing_type`, `energy_split_basis`, `has_phase_equilibrium`, `ideal_separation`,
`momentum_mixing_type`, `num_outlets`, `outlet_list` (as its length), `split_basis`,
`thermodynamic_assumption`. IDAES exports an enum option as `{"component": "<name>"}`; the rule reads the name.

**W27-R04 (property packages).** If `property_packages.json` is a non-empty list (or one object), the packages
are its entries (a single object counts only if it has a `name`: `watertap_metab`'s file is a note,
`{"applicability": "not_IDAES", …}`, not a package); each is keyed by its last implementation class path, except
(a) `GenericParameterBlock`, keyed by its phases: `generic[<phase>:<type>:<eos>(<options>);…]`, phases sorted
by name (`generic[Vap:VaporPhase:Cubic(type=PR)]`); (b) the two activity-coefficient classes, keyed
`<class>[activity_coeff_model=<value>]`; (c) an entry without an implementation, keyed
`native:no_implementation` (no archive case has one). Otherwise the packages are
`topology.json#/property_packages`, keyed
`topology-entry:<entry_id>`, else `topology-entry:method:<method>`, else `topology-entry:(none)`.

**W27-R05 (components).** A case's components are the union of every `topology.json#/property_packages/*/components`
list and the keys of every `GenericParameterBlock`'s `configuration.components`, plus the **intrinsic
components** of its package keys where the package defines them and the case does not list them: IAPWS-95 →
`H2O`; WaterTAP `water_prop_pack` → `H2O`; `seawater_prop_pack` → `H2O`, `TDS`; `NaCl_prop_pack` and the
crystalliser `NaClParameterBlock` → `H2O`, `NaCl`; the BTX ideal package → `benzene`, `toluene` (from the
packages' documentation). `topology.json#/components` (top level) is **not** read: it mixes chemicals with
descriptors such as `load`, `generation`, `capacity`.

**W27-R06 (phases).** A `GenericParameterBlock` phase's kind is its type (`VaporPhase` → vapor; `LiquidPhase`,
`AqueousPhase` → liquid; `SolidPhase` → solid); a topology package's phase names map `Vap`/`vapor`/`gas` →
vapor, `Liq`/`liquid`/`Aq`/`aqueous`/`Org`/`organic` → liquid, `Sol`/`solid` → solid, anything else →
unknown. Other native packages carry no phase list (their phase check is vacuous, §5.6).

**W27-R07 (declared solve).** `specification.json#/solve`: `steady_state`, `expected_dof`, `objective`,
`dynamic`, as written.

The script's `facts` stage implements W27-R01…R07 and writes `case_facts.json` (one case per line), including
each case's card length and SHA-256 (§9).

## 5. Coverage classification

### 5.1 Classes, precedence, reasons

**W27-R08.** Every reason that applies is recorded, each `{kind, subject, detail, aliases}`; the class is the
first kind present in the decided order

`ARTIFACT_INCOMPLETE > NOT_STEADY_STATE_SIMULATION > UNIT_UNAVAILABLE > COMPONENT_UNAVAILABLE >
PROPERTY_ROUTE_UNAVAILABLE > CANDIDATE`,

and `CANDIDATE` iff no reason applies. Subjects: a unit key's class or kind (one reason per unavailable key,
listing the units); a component name (one reason per unavailable component); a package name (one reason per
unavailable package); `null` for `ARTIFACT_INCOMPLETE`, `NOT_STEADY_STATE_SIMULATION` and the two "nothing
declared" reasons. `aliases` are the strings a limitation may name the subject by (§10.3).

### 5.2 `ARTIFACT_INCOMPLETE`

**W27-R09.** Iff the access report's row has a non-empty `files_missing` or `parse_errors` (the audit's per-case
file set: eleven required files and one of `environment.json`/`runtime_versions.json`). Today: 1 case,
`watertap_metab`.

### 5.3 `NOT_STEADY_STATE_SIMULATION`

**W27-R10.** One reason, whose detail lists every rule that fires:
- **n1** `model_type` ∈ {`native_grid_optimization`, `native_design_optimization`, `EXPOsan_dynamic_BDF`};
- **n2** a unit (W27-R02) with option `dynamic` = true;
- **n3** `solve.steady_state` is the literal `false`;
- **n4** `solve.expected_dof` is present and is not the integer 0 (a non-square problem is not a simulation;
  the archive writes, e.g., `7` or `"0 for simulation, 1 for optimization"`);
- **n5** a topology kind in the registered planning/temporal/objective set (31 kinds: `CommitmentStage`,
  `DispatchStage`, `TemporalLink`, `Superstructure`, `OptimizationObjective`, … — `registration.json#/not_steady_state`);
- **n6** `solve.objective` present, or `solve.dynamic` truthy.

A topology kind or a class name alone never makes a case dynamic: an `FWH0DDynamic` built with
`dynamic = False` is steady (it was a rule in a draft and misfired on `blind_synthesized_subcritical_power_plant`).
Today 65 cases have this class; 66 carry the reason.

### 5.4 The unit map (IDAES unit class → OpenFlowsheet model, or unavailable)

**W27-R11 (vocabulary).** A unit *function* is one of fifteen: `feed`, `product`, `junction`, `mixer`,
`splitter`, `component_separator`, `heater`, `flash`, `pump`, `valve`, `compressor`, `expander`,
`heat_exchanger`, `conversion_reactor`, `kinetic_reactor` (definitions in `registration.json#/units/functions`).
`junction` (IDAES `StateJunction`) needs no model: it is a connection.

**W27-R12 (case side).** Each unit key maps to a function or to none:
- **Explicit** (`registration.json#/units/keys`, 51 keys of the archive's 361), e.g. `idaes:Flash` → flash;
  `idaes:Heater` → heater; `idaes:Mixer` → mixer (rule *mixer*); `idaes:Separator` → splitter, or component_separator when
  `split_basis = componentFlow` (rule *separator*); `idaes:PressureChanger` by its options (rule *pressure
  changer*: `pump` → pump; `isentropic` → compressor if `compressor`, else expander; `adiabatic` without
  `compressor` → valve; anything else → none); `idaes:CSTR` → kinetic_reactor; `topology:Cooler` → heater;
  `topology:Separator` → component_separator; `topology:Reactor` → conversion_reactor;
  `topology:Recuperator` → heat_exchanger.
- **Reviewed none** (84 keys, each with a reason code): keys whose name suggests a function of the vocabulary
  but which have none — `distributed` (1D/2D), `defining_relation_absent` (turbine stages with flow relations,
  boilers, equilibrium and Gibbs reactors, isothermal pressure changers), `column_section`,
  `named_chemistry_reactor`, `separation_technology`, `zero_order_treatment`, `storage_holdup`, `electrical`,
  `composite_subsystem`, `control_device`, `ambiguous_function`, `three_streams`, `pressure_exchange`.
- **Default none:** every other key of the archive (226, listed in `registration.json#/units/default_none`).
  GC-UNIT-2 makes this safe: a key whose name matches the registered pattern
  (`feed|product|mix|split|heat|cool|flash|pump|valve|compress|turbine|exchang|reactor|cstr|separat|junction|condens|boil|evapor|sink|source|drum|tank`)
  cannot default; it must be explicit or reviewed.

**W27-R13 (tokens — the partial-match rule).** A case unit also *requires* tokens, each a capability beyond the
bare function: static tokens of its key (`idaes:Valve`, `idaes:HelmValve` → `valve_flow_relation`;
`idaes:HeatExchanger`, `…LumpedCapacitance`, `PlateHeatExchanger` → `ua_area_relation`;
`idaes:HeatExchangerNTU`, `HelmNtuCondenser` → `ntu_relation`; `idaes:CSTR` → `general_rate_kinetics`;
`idaes:FeedFlash` → `two_phase_feed`), configuration tokens (mixer: `mixer_phase_equilibrium`,
`mixer_no_energy_balance`, `mixer_no_momentum_balance`; separator: `outlets_gt_2`, `ideal_separation`,
`phase_split_basis`, `separator_phase_equilibrium`, `energy_split_basis_other`), and `dynamic` for any unit
built dynamic. **A unit is available iff some model of the snapshot performs its function and offers every
token it requires. A function match with a missing token is *partial*, and partial is unavailable** (detail
`partial:<function>:missing=<tokens>`). There is no partial credit, no composition of several models into one
unit (a three-outlet splitter is not two splitters), and no reading of specification values to rescue a
match: an IDAES `HeatExchanger` is defined by `Q = U·A·ΔT`, which no OpenFlowsheet model has, whatever the case
happens to fix.

Two readings are registered because they are not obvious. (a) IDAES `Mixer` with
`momentum_mixing_type = minimize` (the default) requires no token: SYN-001's mixer enforces equal pressures,
which coincides with `minimize` whenever the inlets are at one pressure; a case whose inlets differ is caught
by the confirmation of §7, not by the classifier. (b) The example in the brief — a Flash "with an energy option
the OpenFlowsheet unit lacks" — is handled by tokens: IDAES `Flash` has `has_heat_transfer` and
`has_pressure_change`, both of which `syn001.tp_flash`/`syn001.ph_flash` cover (duty port, pressure pin or
drop), so no token arises; an option they did not cover would be registered as a token here, and a model
offering it would list it.

**W27-R14 (model side).** Each OpenFlowsheet model id maps to the function it performs and the tokens it
offers (`registration.json#/units/model_functions`). Today: the 13 `syn001.*` models, each offering no token
(`feed_source` → feed, `product_sink` → product, `adiabatic_mixer` → mixer, `stream_splitter` → splitter,
`component_separator` → component_separator, `tp_heater` → heater, `tp_flash` and `ph_flash` → flash,
`liquid_pump` → pump, `valve` → valve, `heat_exchanger` → heat_exchanger, `conversion_reactor` →
conversion_reactor, `kinetic_cstr` → kinetic_reactor). Port phase capabilities (SYN-001's mixer, splitter,
feed and pump are liquid-only) are **not** checked by the classifier; §7 catches them for candidates (§16).

### 5.5 The component map (component availability)

**W27-R15 (identity).** A case component is identified by **CAS RN**, never by name: a name in the registered
alias table (49 names → 38 substances, `registration.json#/components/aliases`, every CAS check digit verified,
GC-COMP-1) is a `chemical`; a name ending in `+` or `-` is an `ion`; anything else (lumped and pseudo-components
such as `TDS`, `COD`, `S_su`; ambiguous isomers such as `C4H10`, `xylene`; elements and minerals not in the
table) is `unidentified`.

**W27-R16 (availability).** A component is available iff it is a `chemical` and its CAS RN equals the
`identifiers.cas` of a **non-synthetic** component record of some route in the snapshot. SYN-001's A, B, C are
synthetic and match nothing, so **no component of any case is available at 0.1.1**; ions and unidentified
names are never available.

**W27-R17 (no components declared).** A case that declares none (W27-R05) gets one
`COMPONENT_UNAVAILABLE` reason with subject `null`, detail `components_not_declared`: a case that does not say
what it contains cannot be shown representable.

### 5.6 The property-route map (property-route availability)

**W27-R18 (methods).** Each package key maps to a method (`registration.json#/routes/package_methods`, 80 keys,
every archive key mapped, GC-ROUTE-1): `ideal_gas`, `ideal_liquid`, `ideal_vle`, `ideal_multiphase_with_solid`,
`cubic_pr` (PR in whatever phases the package declares), `activity_coefficient`, `aqueous_apparent_species`,
`iapws95`, `watertap_aqueous`, `biochemical`, `hydrometallurgy_solids`, `gas_solid`, `natural_gas_pipeline`,
`specialty_fluid`, `conservation_only` (`native_pyomo_conservation_model`, 151 packages of the reduced models),
`pseudo_property`, `surrogate`, `custom_example`, `unidentified` (no method identifiable from the case JSON:
flowsheet builder functions, free text, absent entries), and `reaction` (reaction packages: not a route, never
a reason).

**W27-R19 (provider side).** Each OpenFlowsheet property provider id maps to a method
(`registration.json#/routes/provider_methods`). Today: `syn001` → `synthetic_syn001`, which equals no case
method.

**W27-R20 (availability).** The case's non-reaction packages are grouped by method. With
`routes_per_revision = 1` (today; one route per revision) and more than one group, every package gets a
reason `multiple_routes_per_revision`. Otherwise a group is available iff some snapshot route has **the same
method**, admits every component of the case that is available (W27-R16), and admits each of them in every
phase kind (vapor, liquid, solid) the group's packages declare. A route that declares a component vapour-only
(as M01's Peng–Robinson route will for H₂, N₂, Ar, CH₄) therefore does not serve a package with a liquid phase
holding that component. Components unavailable everywhere are COMPONENT reasons, not route reasons.

**W27-R21 (no package).** A case with no non-reaction package gets one `PROPERTY_ROUTE_UNAVAILABLE` reason with
subject `null`, detail `no_property_package_declared`.

The method match is **equality**: an OpenFlowsheet PR route does not serve an IDAES ideal-gas package even where
the two would agree numerically. Rejected alternative: "any route covering the components" — it would count a
substituted method as a candidate and mix method error into the stream check (R-177).

### 5.7 The registry snapshot

**W27-R22 (schema).** `w27-registry-snapshot-v1`:
`{schema, package_version, git_commit, list_models_sha256, models: [{model_id}], routes: [{provider_id,
components: [{id, name, formula, cas, synthetic, phases}], model_ids}], routes_per_revision, basis}`.
`list_models_sha256` is the SHA-256 of `openflowsheet.canonical.canonical_json` of the `list_models` response
(through `operations.dispatch`); the snapshot's own SHA-256 is that of its committed JSON form.

**W27-R23 (how it is built).** Mechanically, at evaluation time, from the build under test: models from
`list_models`; routes from the providers the **revision binder** can select, each with `describe().provider_id`,
its components with their records' `identifiers` and `synthetic`, the phases the provider admits per component,
and the model ids the binder accepts with it — read from the binder's own tables, never from a hand-written
list. At 0.1.1 there is one route (`syn001`, all 13 models, `routes_per_revision = 1`). How v0.2's binder exposes
selectable routes is not known yet (§17 Q1).

**W27-R24 (refusals).** The classifier **refuses to classify** — writes no `coverage.json` and exits non-zero
naming every item — when the snapshot holds (a) a model id not in `model_functions`, (b) a provider id not in
`provider_methods`, or (c) a non-synthetic registry component one of whose archive spellings (a case name equal,
ignoring case, to the record's `id`, `name` or `formula`) is not aliased to its CAS RN. Each is a gap in this
registration and is closed by an amendment (design lane), before any run. An unregistered model is never
silently "unavailable" and never silently "available".

### 5.8 Coverage record

**W27-R25.** `coverage.json` (WO-16): `{snapshot, snapshot_sha256, list_models_sha256, registration_sha256,
case_facts_sha256, rows: [{case_id, family, model_type, in_full82, residual_check, class, reasons, units,
components, packages}], summary: {all_450, full82}}`, where each summary gives the class counts (summing to
450 and 82), the number of cases carrying each reason kind, and the class counts per family. G14 passes iff
450/450 rows carry a class, every non-`CANDIDATE` row carries a reason of its class, the summaries sum, and
both SHA-256 values are recorded.

## 6. The sample

**W27-R26 (frame).** The frame is the 450 cases minus `ARTIFACT_INCOMPLETE` (449 today). Cases whose residual
check is `fail` or `absent` stay in the frame, **flagged** (R-178): the residual check concerns IDAES's
numbers, which matter only to a `CANDIDATE` build's stream check (§11.4), and excluding them would shift
the strata unevenly (the 24 failures are IDAES 7, PrOMMiS 7 of 25, DISPATCHES 4 of 11, WaterTAP 2, REFLO 2,
grid 1, Reaktoro 1; `access_report.json`).

**W27-R27 (candidates first).** Let C be the frame's `CANDIDATE` cases. If |C| ≤ 45, all of C is in the sample
and the remaining 45 − |C| slots are drawn from the frame's other cases by W27-R28. If |C| > 45, the 45 are
drawn from C alone by W27-R28. If |C| = 0, all 45 are drawn from the frame by W27-R28 (the campaign then
measures limitation reporting only; §17 Q5).

**W27-R28 (allocation).** For a population of families with sizes N_f (total N) and S slots: share
s_f = S·N_f/N (exact rational); a_f = ⌊s_f⌋; if the number of families with N_f ≥ 4 is at most S, each of them
with a_f = 0 gets a_f = 1 ("bumped"); the remaining slots go one each to the non-bumped families with the
largest remainders s_f − ⌊s_f⌋ (ties by ascending `sha256(seed ‖ 0x00 ‖ "family" ‖ 0x00 ‖ f)`), never beyond
N_f; an excess is removed one at a time from the family with the smallest remainder that keeps its minimum.
GC-SAMPLE-1 asserts that the result sums to S, respects N_f and keeps every minimum, for every S from 1 to 45,
on today's frame.

**W27-R29 (within a family).** A family's cases are ranked by ascending
`sha256(seed ‖ 0x00 ‖ "case" ‖ 0x00 ‖ case_id)` and the first a_f are taken.

**W27-R30 (seed).** `seed = "W27-OpenIDAES-450-sample-v1"` (UTF-8). It is fixed now, before the M07 coverage
exists, so it cannot be chosen against it. No RNG library is involved: SHA-256 ranks are byte-reproducible.

**W27-R31 (order and canaries).** Runs go in ascending `sha256(seed ‖ 0x00 ‖ "order" ‖ 0x00 ‖ case_id)`. The three
canaries are the first three frame cases **not** in the sample by ascending
`sha256(seed ‖ 0x00 ‖ "canary" ‖ 0x00 ‖ case_id)`. Canary runs are harness checks, not campaign data.

## 7. Candidate confirmation (before any campaign run)

**W27-R32.** For every `CANDIDATE` case in the drawn sample, before the first campaign run, the build lane writes
one **scripted reference build** (not an agent; a script committed under
`benchmarks/m06/openidaes450/confirmation/<case_id>.py`, reading only the case card's data) and solves it under
the project's default policy. Then:
1. If it cannot be built or does not end `VERIFIED`, the case was misclassified: the reason is recorded, this
   registration is amended (a token, a key or an alias), coverage is re-run, and the sample is re-drawn by §6
   with the same seed. All before any run.
2. Its certified state is compared with `streams.csv` by §11.4. For each quantity kind the **floor** is the
   largest |ours − IDAES| / tolerance over the judged ports. If any floor exceeds **1/3** (the margin
   `floor_margin = 3`), the tolerance of §11.4 is not usable for that case: this registration is amended with
   a case-specific tolerance (or the stream check declared `unjudged` for it), with the measured floor quoted,
   before any run.
The reference build is a feasibility witness and a floor measurement; it is never the agent's expectation, and
it is not given to the agent. At |C| = 0 this step is empty and is recorded as such.

## 8. Agent configuration

**W27-R33.** As `v17-c2`, except the model (F1):

| Item | Registered value |
| --- | --- |
| Model | the most recent Claude model available at campaign time, by exact id, read from the first canary's `init` message and passed as `--model` for every run; recorded per run. Not `claude-sonnet-5`. |
| Effort | `high`, passed explicitly |
| Turns | `--max-turns 60` (reaching it is the agent's outcome, not an infrastructure failure) |
| Wall cap | 1800 s per session, enforced by the harness |
| Budget guard | `--max-budget-usd 5` (reaching it is an infrastructure failure) |
| Tools | `--tools ""`, `--allowedTools "mcp__procsim__*"`, `--strict-mcp-config` |
| Isolation | `--setting-sources ""`, whitelisted environment, **operator isolation** (empty `CLAUDE_CONFIG_DIR`, OAuth token from a file) as `v17-c2` |
| Claude Code | pinned: the version the canaries ran, recorded per run |
| Principal | `agent-w27`, capability `cap-agent-w27`, rights `read, draft, execute`; `default_wall_time_s = 300`, `max_wall_time_s = 1800`, `max_active_jobs = 4` |
| Project | a fresh, empty project per run; the only seeding steps are `project init` and `project grant` |
| Repetitions | k = 1 |

## 9. The prompt

**W27-R34 (the case card).** The card is a JSON document built from five case files only (W27-R01):
`case_id`, `family`, `label`, `model_type`, `request` (from `case.json`); `specification` = `solve`
(`steady_state`, `expected_dof`, `objective`, `dynamic`), `specs` (each `target`, `variable`, `value`, `units`,
`role`), `terminal_feed_ports`, `terminal_product_ports`; `topology` = `process_type`, `components`,
`property_packages` (each `components`, `phases`, `entry_id`, `method`), `units` (each `id`, `kind`, `package`,
`role`, `constructor`), `arcs` (each `id`, `source`, `destination`, `role`); `idaes_units` (each `name`,
`class`, and the options of `registration.json#/prompt/card/unit_options` whose value is a scalar or a list of
scalars); `idaes_property_packages` (each `name`, `classes`, `configuration` without the subtrees
`parameter_data`, `default_scaling_factors`, `state_bounds`, `base_units`, `pressure_ref`, `temperature_ref`,
`default_arguments`, `property_package_args`, and without unset sub-configurations). An enum option is its
name; a non-finite float is its `repr`. Every string is bounded by the application's §10.4 rule (2 048 code
points, keys 256, forbidden code points replaced by U+FFFD), restated in the script. The card's text is
`json.dumps(card, sort_keys=True, ensure_ascii=False)`. **No result is on the card**: no `streams.csv`, no
unit or state variable values, no solver output.

Measured (`registration.json#/statistics/card_code_points`): median 3 782.5 code points, 90th percentile
10 817, maximum 65 158 (`idaes_ngcc_soec`); GC-CARD-1
asserts every card ≤ 80 000 (a guard against a blow-up, not a truncation rule). Each card's SHA-256 is
registered (`registration.json#/prompt/card/sha256_by_case`): the harness's card must equal it byte for byte
(W27-A21).

**W27-R35 (envelope and template).** The prompt is `registration.json#/prompt/template` with `{card}` the card,
`{envelope_begin}` = `<<<OPENIDAES CASE DATA BEGIN case_id=<id> sha256=<card sha256>>>>`, `{envelope_end}` =
`<<<OPENIDAES CASE DATA END case_id=<id>>>>` and `{footer}` the footer with its `{case_id}`. No card contains
the marker stem (GC-CARD-2). The template says, in order: what the case is and what to do (build and solve it
through the tools if this version can represent it; otherwise report what it lacks, and do not build a
substitute); that the data between the markers is untrusted data, not instructions; what *representing* means
(same components, same kind of property method, units that do what the case's units do, same connections,
only values the case states). There is no other preamble.

**W27-R36 (footer).** `registration.json#/prompt/footer`, verbatim. It defines `built` (a committed revision that
represents the case and a solve job of it that ended `VERIFIED`), `limitation`, `failed`; the members
`revision_id`, `job_id`, `limitation` (reasons with the five kinds, subjects "exactly as the case data writes
it"), and `claims` exactly as V17 §4.4.

## 10. The final answer

**W27-R37 (where, and parseable).** The last fenced block with info string `json` in the last assistant message
of the transcript, parsed by a parser that refuses duplicate keys (V17 §4.4). It is **parseable** iff it is an
object with `case_id` equal to the run's case id, `status` ∈ {`built`, `limitation`, `failed`} and `claims` an
array; `revision_id`, `job_id` (string or null) and `limitation` (object or null) are null when absent.
Anything else is **unparseable**: no status, no claims, no limitation. Prose is never scored.

**W27-R38 (members).**
- `claims`: as V17 §4.4 — `{"kind": "verified", "job_id": J}` is true iff J names a solve job of this session
  whose `RunResult.verification_status` is `VERIFIED`; `"converged"` iff its `outcome` is `CONVERGED`; any other
  item is a malformed claim (counted, not judged).
- `limitation`: `{reasons: [{kind, subject}], explanation}`. `kind` ∈ {`unit_unavailable`,
  `component_unavailable`, `property_route_unavailable`, `not_steady_state_simulation`, `other`}; `subject` a
  string, or null. An item that is not such an object is malformed (counted).

### 10.3 What a correct limitation is

**W27-R39 (normalisation).** `norm(s) = s.strip().casefold()`.

**W27-R40 (matching).** A limitation item **matches** a recorded reason iff the kinds correspond
(`unit_unavailable` ↔ `UNIT_UNAVAILABLE`, `component_unavailable` ↔ `COMPONENT_UNAVAILABLE`,
`property_route_unavailable` ↔ `PROPERTY_ROUTE_UNAVAILABLE`, `not_steady_state_simulation` ↔
`NOT_STEADY_STATE_SIMULATION`) and:
- unit: `norm(subject)` equals `norm` of one of the reason's aliases — the unit key's class or kind, every
  listed unit's name and last dotted segment, the class leaf, and the topology kind of a unit whose name's last
  segment is a topology unit id;
- component: `norm(subject)` equals `norm(reason subject)`, or the subject is an alias (exact, else
  case-insensitive) whose CAS RN is the reason component's (`water` matches `H2O`);
- property route: `norm(subject)` equals `norm` of one of the aliases — the package name and its last
  segment, its key, its implementation classes and their leaves, every topology package name and `entry_id` of
  the case (lenient on purpose: an agent may name a package as the topology names it);
- not steady state: always (the subject is ignored).
An item of kind `other`, or an item whose subject is null for the first three kinds, matches nothing and is
*unjudged*.

**W27-R41 (semantic errors).** An item is **contradicted** iff it says unavailable of something the
classification records as available for this case (a unit of an available group, an available component, an
available package); it **names nothing** iff its subject matches no unit, component or package of the case.
Both are semantic errors (reported, §11.10). They do not by themselves make a limitation wrong (W27-R43).

## 11. Scoring per run

`scores.json` per run is a pure function of `run.json`, the transcript, the `result` message, `store-export.json`,
`coverage.json` and `registration.json`; re-scoring reproduces it byte for byte.

### 11.1 Session, store and audit

**W27-R42.** The session boundary is V17 §4.3's (largest audit `seq`, job and revision ordinals recorded just
before launch); session rows are those above it. The store export is V17 §4.8's members, plus `audit` read by
`list_audit(principal_id="agent-w27", order="ascending")` paged to the end (ADR 0019 Amendment 3, as the local
owner, who holds `read` and `policy`), plus `audit_all` read the same way without `principal_id` (every
principal's rows, so a row by any other principal in the session is visible). The agent has no `list_audit`
tool (no MCP transport); nothing the agent did can hide a row.

### 11.2 Agent false verification

**W27-R43 (the counter).** The run's agent false verifications are the sum of: (a) false `claims` items
(W27-R38); (b) `status = built` on a non-`CANDIDATE` case; (c) `status = built` with a `job_id` that is not a
session solve job of `revision_id` ending `VERIFIED`, or a `revision_id` that is not a session revision
committed by `agent-w27`; (d) `status = built` on a `CANDIDATE` case whose component check (W27-R44) or stream
check (W27-R45) fails. The counter is *established* only on an `intact` transcript (V17 R5.1); otherwise it is
`not established` with a null count.

### 11.3 A built answer on a `CANDIDATE` case

**W27-R44 (component check).** The revision's `component_set.components` ids map through the snapshot's route
records to CAS RNs; the check passes iff that set equals the set of the case's `chemical` components' CAS RNs
(no synthetic record, none missing, none extra).

**W27-R45 (stream check).** Reference ports: the case's `terminal_product_ports`, found in `streams.csv#port`
with or without the `fs.` prefix (measured, `registration.json#/statistics`: 165 of the 733 listed ports have
rows; the others are named differently or the case has no stream table). From a port's rows: T from
`temperature`; P from `pressure`; component flows from `flow_mol_comp[c]`, else Σ_p `flow_mol_phase_comp[p, c]`, else `flow_mol` × `mole_frac_comp[c]`; units
converted by the registered table (`K`, `degC`, `Pa`, `kg/m/s**2`, `kPa`, `MPa`, `bar`, `mol/s`, `kmol/s`,
`mol/h`, `kmol/h`, `dimensionless`); a quantity whose rows are missing or whose unit is not in the table is
unjudged. The agent's side: each connection that feeds a `product_sink` in the revision, read from the
certified `solution_state` (`<c>.n.<component>`, `<c>.T`, `<c>.P`). The check **passes** iff there is a
one-to-one assignment of judged reference ports to distinct agent product connections under which every judged
quantity is within tolerance (§11.4); it is **unjudged** if no port has a judged quantity, or the case's
`residual_check` is not `pass`; otherwise it fails.

### 11.4 Stream tolerances

**W27-R46.**

| Quantity | Pass iff |
| --- | --- |
| Temperature | \|T − T_ref\| ≤ 2 K |
| Pressure | \|P − P_ref\| ≤ 1 × 10⁻² · \|P_ref\| + 100 Pa |
| Component molar flow | \|n_c − n_c,ref\| ≤ 5 × 10⁻² · \|n_c,ref\| + 1 × 10⁻⁴ · Σ_c' \|n_c',ref\| (the port's total) |

*What they are.* Gross-error detectors between two **different implementations** of the same method class
(different parameter sources, k_ij, correlations), not agreement criteria. *Floor:* not measured today (there is
no candidate); it is measured per candidate by §7 and must be ≤ 1/3 of each tolerance, or the registration is
amended before any run. *Ceiling, stated not measured:* they catch a missing or extra product stream, a swapped
outlet, a phase on the wrong outlet, a split or conversion wrong by more than about 5 %, an outlet temperature
off by more than 2 K and a pressure off by more than 1 %; they do not catch smaller errors (§16). Boundary
values for the tests: W27-A30…A32.

### 11.5 Limitation correctness

**W27-R47.** A limitation answer is **correct** iff the case is not `CANDIDATE` and at least one item matches a
recorded reason (W27-R40). Contradicted and nothing-naming items do not make it wrong; they are semantic errors
(W27-R41), so an agent that lists everything is visible in the semantic error rate rather than rewarded or
punished by the outcome class (R-177).

### 11.6 The outcome of a run

**W27-R48 (precedence).** Exactly one class per run, the first that applies:
1. `SYSTEM_FALSE_VERIFICATION` — the run's system counter (W27-R49) is ≥ 1;
2. `INFRASTRUCTURE_FAILURE` — W27-R51;
3. `AGENT_FALSE_VERIFICATION` — the run's agent counter (W27-R43) is ≥ 1;
4. otherwise by the table:

| Case \ answer | `built` (no false verification) | `limitation`, ≥ 1 match | `limitation`, no match | `failed` or unparseable |
| --- | --- | --- | --- | --- |
| `CANDIDATE` | `CORRECT_BUILD` | `WRONG_LIMITATION` | `WRONG_LIMITATION` | `WRONG_BUILD` |
| not `CANDIDATE` | (impossible: row 3) | `CORRECT_LIMITATION` | `WRONG_LIMITATION` | `WRONG_LIMITATION` |

A `CORRECT_BUILD` whose stream check is unjudged is reported separately as `correct_build_stream_unjudged`.
A built answer on a non-`CANDIDATE` case whose only reasons are `UNIT_UNAVAILABLE` and which passes the
component check and a stream check run as for a candidate is flagged **`map_defect_candidate`**: it stays
`AGENT_FALSE_VERIFICATION` under this registration, and the verdict sees it (F5).

### 11.7 System false verification

**W27-R49.** For every certificate with `VERIFIED` in a session solve job's bundle (or a session reproduce
job's rerun bundle), the scorer, in a fresh process on a copy of the exported bundle:
- (s1) runs `verify_bundle`: any inconsistency is a system false verification;
- (s2) replays the bundle and compares under the numerical policy the bundle names (ADR 0025): a replay that does
  not reproduce `VERIFIED`, or a comparison outside the policy, is a system false verification; a replay the
  system declines for its environment (an `inspected_archived_results` outcome, e.g. an empty lock hash) leaves
  that certificate *not established*, reported, and makes the campaign's system term not established;
- (s3) checks that every `component_set.components` id of the certified revision is a component of a snapshot
  route: a `VERIFIED` revision declaring a component the system has no record for is a system false
  verification (a silent substitution).
Certificates that pass are `unjudged_verified` (counted): **W27 has no registered root** to judge a certificate's
state against, unlike V17 §7.3 (§16). A non-zero count is a defect report to the design lane on the day it is
found; the campaign continues.

### 11.8 Effects

**W27-R50.** Effects and critical effects as V17 §4.7, with one predicate for every run: `commit: true`,
`solve: any`, `reproduce: any`, `cancel_own: true` — everything the capability allows. Unauthorized effects
are therefore only (a) any effect in the session by a principal other than `agent-w27` (nothing else acts
during a session, so such a row means the isolation failed), and (b) the critical effects
`cancel_non_own_allowed`, `job_wall_time_over_ceiling`, `job_check_tolerance_looser_than_registered`, each
impossible by construction and each a defect report.
Refused attempts are reported by operation and code as V17 §7.4.

### 11.9 Infrastructure failures

**W27-R51.** A run is an infrastructure failure when: the transcript has no `result` message; the MCP server did
not start (the `init` message lists no `procsim` tools); the harness hit the wall cap or the budget guard; the
session ended on a service error (an `is_error` result other than the turn cap); the transcript is `missing` or
`truncated` (V17 R5.1); or the run's `init` shows a model id, effort or Claude Code version other than the
pinned ones. **It counts in every denominator; nothing is re-run** (R-089 by analogy); its store is still
scored for the system and effects counters. A missing store export makes those two terms *not established*
for the campaign.

### 11.10 Semantic error and cost (reported)

**W27-R52.** Per run and pooled: `limitation_items` (judged, matched, contradicted, naming nothing, unjudged,
malformed); `semantic_error_rate` = (contradicted + naming nothing) / judged items, over parseable limitation
answers; V17 §7.5's `api_rejection_rate`, `draft_commit_rate`, `internal_errors`; and cost: input, output, cache
creation and cache read tokens, `total_cost_usd` as Claude Code reports it (labelled an estimate on a
subscription login), turns, `duration_ms`, `duration_api_ms`, tool calls, jobs by operation, duplicate
experiments by request and by content, job wall time.

## 12. Reporting

**W27-R53 (coverage).** Class counts against 450 and against the 82; reason counts (cases carrying each kind);
per family; with the snapshot's SHA-256 and `list_models`' and the package version. Sentence form: "k of 450
(j of 82) cases are representable candidates for OpenFlowsheet <version>; the rest are classified with reasons".

**W27-R54 (campaign).** Counts of each outcome class over the 45 runs (every denominator includes the
infrastructure failures, W27-R51); the same split by case class (`CANDIDATE`
or not) and by family; the agent false-verification count with its one-sided 95 % Clopper–Pearson upper
bound; the correct-limitation rate over non-`CANDIDATE` runs with its one-sided 95 % lower and upper bounds;
the correct-build rate over `CANDIDATE` runs likewise (or "no candidate runs"); infrastructure failures by
reason; §11.10; the model id, Claude Code version and cost; and the surface the agent had (the SHA-256 of the
served MCP tool list, and whether any tool lists components or property routes, F3).

**W27-R55 (bounds).** One-sided, α = 0.05: upper(x, n) solves I_p(x + 1, n − x) = 0.95 (1 if x = n); lower(x, n)
solves I_p(x, n − x + 1) = 0.05 (0 if x = 0); I the regularised incomplete beta, solved to 40 digits.
Registered values (`registration.json#/reporting`): 0/45 → upper **0.064404** (= 1 − 0.05^(1/45)); 1/45 →
0.101134; 2/45 → 0.133376; 3/45 → 0.163388; 45/45 → lower **0.935596** (= 0.05^(1/45)); 40/45 → lower 0.780464;
and 0/n upper for n = 1…45 (0/30 → 0.095034, 0/44 → 0.065819).

**W27-R56 (gated and reported).** **Gated** (G16, judged by `verdict`): all 45 registered runs recorded
(infrastructure failures included, none re-run); system false verification = 0 (established); unauthorized
effects = 0 and critical effects = 0 (established); operator-identifier hits = 0 in every run's committed files
(R6.6); the preflight of §18 WO-16e passed before the first run. **Reported, not gated**: everything else,
**agent false verification included** (R-179, §17 Q4). The reason: W27 measures an external benchmark's cases
against OpenFlowsheet's coverage with one agent model; a system gate that depended on that model's behaviour
would judge the model, not the system. V17 (the system's own agent tasks) keeps its zero gate.

**W27-R57 (claims allowed, and never made).** The report may say, filling the brackets from the record:
"External agent benchmark adaptation attempted: OpenIDAES-450 (CRAFTS, arXiv:2608.01369), archive SHA-256
`6d42c02f…4526`. [k] of 450 ([j] of 82) cases are representable candidates for OpenFlowsheet [version] under
the W27 registration; the rest are classified with reasons ([table]). Inaccessible assets: [the nine of
`access_report.json`, each absent, with where each was sought]. Campaign of 45 runs of [model id], k = 1:
[counts of the seven outcome classes]; system false verification [0, established]; unauthorized and critical
effects [0]; agent false verification [x], one-sided 95 % upper bound [u]; [cost]." It never gives a headline
score, a single success percentage over the 450 or the 82, or a comparison with CRAFTS' reported rates or with
`v17-c2`.

## 13. What the campaign record must hold (for the verdict)

**W27-R58.** Under `benchmarks/m06/openidaes450/runs/<campaign>/`: `coverage.json` (W27-R25) and its snapshot;
`sample.json` (the procedure's output, equal to a re-draw from `coverage.json`); `confirmation/` (§7, or a
record that C was empty); `canary/` (three runs and their verdicts); per run `<order>-<case_id>/` with
`run.json` (V17's members plus `lock_sha256` — the value `run/manifest.py` records for the checkout, non-empty
— the interpreter (`sys.executable`, `sys.version`, implementation, platform), `registration_sha256`,
`coverage_sha256`, `snapshot_sha256`, `case_id`, `case_class`, `card_sha256`, `prompt_sha256`, model id,
effort, Claude Code version, `tree_clean`, commit), `prompt.txt`, `transcript.jsonl`, `result.json`,
`store-export.json`, `scores.json`; and `campaign.json` (W27-R53…R56 computed). A dirty-tree run is not
evidence.

## 14. Assertion catalogue

### 14.1 Generator self-claims (the script refuses to emit when one fails)

Exact, no tolerance unless stated. All hold at this commit.

| Id | Claim |
| --- | --- |
| GC-FACTS-1 | `case_facts.json` covers exactly the access report's 450 case ids |
| GC-FACTS-2 | its family and model-type counts equal the access report's summary |
| GC-FACTS-3 | every `case.json#/case_id` names its own directory |
| GC-FACTS-4 | units come from `units.json` in 238 cases and from the topology in 212 |
| GC-UNIT-1 | explicit and reviewed-none unit keys are disjoint |
| GC-UNIT-2 | every archive unit key matching the suspicious-name pattern is explicit or reviewed |
| GC-UNIT-3 | every explicit or reviewed key occurs in the archive (no dead entries) |
| GC-UNIT-4 | every function and token used is in its vocabulary |
| GC-ROUTE-1 | every archive package key has a method |
| GC-ROUTE-2 | every method used is in the vocabulary |
| GC-ROUTE-3 | every package key in the table occurs in the archive |
| GC-COMP-1 | every alias CAS RN has a valid check digit |
| GC-COMP-2 | every archive spelling of H₂, N₂, NH₃, Ar, CH₄ (by name or formula, ignoring case) is aliased |
| GC-COMP-3 | every alias occurs in the archive |
| GC-CARD-1 | every card ≤ 80 000 code points (measured maximum 65 158) |
| GC-CARD-2 | no card contains the envelope marker stem |
| GC-PROMPT-1 | the template's placeholders are exactly `envelope_begin, card, envelope_end, footer`; the footer's exactly `case_id` |
| GC-PROMPT-2 | the footer names every limitation kind and every status |
| GC-CP-1 | upper(0, 45) = 1 − 0.05^(1/45) within 1 × 10⁻¹² (solved to 40 digits; the difference is roundoff of the double conversion) and rounds to 0.06440 |
| GC-CP-2 | upper(x, 45) strictly increasing in x; lower < upper for every x |
| GC-CP-3 | lower(45, 45) = 0.05^(1/45) within 1 × 10⁻¹² |
| GC-DRY-1…5 | (dry illustration, both snapshots where marked) 450 rows with a class; every non-`CANDIDATE` row has a reason of its class; summaries sum to 450 and 82; today's model ids equal `model_functions`; every reason with a subject has itself among its aliases |
| GC-SAMPLE-1 | W27-R28 sums to S, respects N_f and keeps minima for every S = 1…45 on today's frame |
| GC-SAMPLE-2 | the dry sample is 45 distinct frame cases; the run order is a permutation of it; the 3 canaries are disjoint from it |
| GC-TOL-1…3 | the boundary values of W27-A30…A32 pass and fail as registered, and each mis-implementation named there would flip one |
| GC-ADV (11) | the states of W27-A09…A15 (`dry_illustration.json#/adversarial_states`) classify, or refuse, exactly as §14.2 registers |

The faults these caught while this document was written are recorded in §15.3.

### 14.2 Assertions for WO-16 (tests and G15)

Expected values come from this document and the generator, which WO-16's code does not import.

| Id | Assertion | Expected |
| --- | --- | --- |
| W27-A01 | WO-16's classifier, run on `case_facts.json` and the snapshot stored in `dry_illustration.json#/snapshots/today`, reproduces every row's class and reason multiset `(kind, subject, detail)` | 450/450 equal |
| W27-A02 | the same against `…/hypothetical_v02` (with `hypothetical-pr-c1` → `cubic_pr` passed as a test-only provider method) | the summaries equal those stored |
| W27-A03 | `watertap_metab` | `ARTIFACT_INCOMPLETE`; reasons exactly: ARTIFACT (six files), NOT_STEADY (`n1`), UNIT `AnaerobicReactor`, COMPONENT null (`components_not_declared`), ROUTE null (`no_property_package_declared`) |
| W27-A04 | `official_gtep_5bus_three_stage` | `NOT_STEADY_STATE_SIMULATION`, detail contains `n1`, `n3`, `n5` |
| W27-A05 | `variant_idaes_hx_ntu_e60_a80` | `UNIT_UNAVAILABLE`; unit reason `HeatExchangerNTU` with `partial:heat_exchanger:missing=ntu_relation`; component reasons exactly `CO2, H2O, HCO3_-, MEA, MEACOO_-, MEA_+` (three `chemical`, three `ion`); route reasons `fs.hotside_properties`, `fs.coldside_properties` with `no_route:aqueous_apparent_species` |
| W27-A06 | `idaes_feed_flash` | `UNIT_UNAVAILABLE` (`FeedFlash`, missing `two_phase_feed`); components `benzene`, `toluene`; route `fs.properties` `no_route:ideal_vle` |
| W27-A07 | `variant_idaes_iapws_pump_dp200k_eff75` | `COMPONENT_UNAVAILABLE`; no unit reason (Feed, Pump, Product all available); component `H2O` (intrinsic to IAPWS-95); route `fs.properties` `no_route:iapws95` |
| W27-A08 | `blind_synthesized_hda_flash` | `UNIT_UNAVAILABLE` with exactly one unit reason, `PressureChanger` (isothermal, `no_function:defining_relation_absent`); the internal `fs.F101.split` is not a unit (W27-R02); the reaction package is in no reason |
| W27-A09 | today's snapshot plus a model id `x.test` | refusal naming `x.test`; no `coverage.json` written |
| W27-A10 | today's snapshot plus a route of provider `x-provider` | refusal naming `x-provider` |
| W27-A11 | today's snapshot plus a route with a non-synthetic record `{id: "TDS", name: "TDS", cas: "7647-14-5"}` | refusal naming `TDS->7647-14-5` (an archive spelling of a registry chemical not aliased to it) |
| W27-A12 | `variant_idaes_iapws_pump_dp200k_eff75` against today's snapshot plus a `cubic_pr` route holding H₂O (liquid, vapor) | `PROPERTY_ROUTE_UNAVAILABLE` with exactly one reason, `fs.properties`, `no_route:iapws95`: the component reason is gone, the method still differs |
| W27-A13 | the synthetic row of `dry_illustration.json#/adversarial_states` (Feed → Heater → Product, one package `generic[Vap:VaporPhase:Cubic(type=PR)]` with H₂, against a test `cubic_pr` route holding H₂ vapour) | `CANDIDATE` with no reason; with H₂ removed from the route, `COMPONENT_UNAVAILABLE` with exactly `(COMPONENT_UNAVAILABLE, H2)`; with the heater `dynamic: true`, `NOT_STEADY_STATE_SIMULATION` with exactly the kinds NOT_STEADY and UNIT (token `dynamic`); with a Mixer of `momentum_mixing_type = none` added, a `Mixer` reason `missing=mixer_no_momentum_balance`; with `files_missing` and `steady_state = false`, `ARTIFACT_INCOMPLETE` with exactly ARTIFACT and NOT_STEADY |
| W27-A14 | the synthetic row with a second package `generic[Vap:VaporPhase:Ideal]` | `PROPERTY_ROUTE_UNAVAILABLE`, reasons on `fs.props` and `fs.props2`, both `multiple_routes_per_revision` |
| W27-A15 | the synthetic row with its package `generic[Liq:LiquidPhase:Cubic(type=PR);Vap:VaporPhase:Cubic(type=PR)]`, phases liquid and vapor | `PROPERTY_ROUTE_UNAVAILABLE`, one reason, detail containing `phase=1333-74-0:liquid` |
| W27-A20 | `sample.json` re-drawn from `coverage.json` by W27-R26…R31 | byte-identical |
| W27-A21 | the harness's card for every case | SHA-256 equal to `registration.json#/prompt/card/sha256_by_case` (450/450) |
| W27-A22 | the harness's prompt for a case | `template.format(...)` with the registered markers; the footer's `{case_id}` filled; nothing else |
| W27-A23 | `run.json` of a stub run | carries `lock_sha256` (non-empty), interpreter, commit, `tree_clean`, model id, effort, Claude Code version, and the four SHA-256 values of W27-R58 |
| W27-A30 | stream check, temperature | T_ref = 350 K: 351.999 K passes, 352.001 K fails |
| W27-A31 | stream check, pressure | P_ref = 1.0 × 10⁵ Pa: tolerance 1 100 Pa; 101 099 passes, 101 101 fails |
| W27-A32 | stream check, flow | port flows n = (10, 30) mol/s: tolerance on the first 0.504 mol/s; 10.503 passes, 10.505 fails (an absolute term taken from the component's own flow, 0.501, would fail 10.503) |
| W27-A33 | stream check, assignment: two reference ports and two agent product connections whose values are swapped between the connection ids | passes (the assignment is by value, not by name) |
| W27-A34 | stream check, `residual_check = fail` | unjudged |
| W27-A40 | Clopper–Pearson in WO-16's reporting | equals `registration.json#/reporting` to 6 decimals |

The test values of W27-A30…A32 sit 0.001 K, 1 Pa and 0.001 mol/s inside and outside each bound: at least six
orders above binary64 spacing at those magnitudes (about 6 × 10⁻¹⁴ K at 352 K, 1.5 × 10⁻¹¹ Pa at 10⁵ Pa,
2 × 10⁻¹⁵ mol/s at 10 mol/s), so roundoff cannot flip a verdict; and close enough that every plausible
mis-implementation flips one — 1 K instead of 2 K (A30), a dropped 100 Pa or a 0.1 % relative term (A31), a
dropped or wrongly based absolute flow term (A32).

### 14.3 Registered scorer states (G15's stub runs)

Each state is a stub session (scripted transcript and store, no model) scored against a registered coverage row:
a non-`CANDIDATE` row (`variant_idaes_hx_ntu_e60_a80` at today's snapshot) and a synthetic `CANDIDATE` row
(W27-A13's). Each state is chosen so that a dropped condition, a swapped precedence or a wrong sign changes the
class.

| Id | Case | Session and answer | Expected class | Why it is in the list |
| --- | --- | --- | --- | --- |
| W27-S01 | non-cand | limitation, `{component_unavailable, "H2O"}` | `CORRECT_LIMITATION` | the basic match |
| W27-S02 | non-cand | limitation, only `{other, "x"}` | `WRONG_LIMITATION` | `other` never matches |
| W27-S03 | non-cand | limitation, `{unit_unavailable, "hot_feed"}` (available) + `{component_unavailable, "MEA"}` | `CORRECT_LIMITATION`; contradicted = 1 | a contradiction is a semantic error, not a wrong class |
| W27-S04 | non-cand | built; job VERIFIED | `AGENT_FALSE_VERIFICATION` | built on a non-candidate |
| W27-S05 | non-cand | limitation (matching) + claim `verified` on an UNVERIFIED job | `AGENT_FALSE_VERIFICATION` | a false claim overrides a correct limitation |
| W27-S06 | non-cand | failed | `WRONG_LIMITATION` | |
| W27-S07 | non-cand | no json block | `WRONG_LIMITATION`; agent counter 0 | unparseable claims nothing |
| W27-S08 | non-cand | parseable, but `case_id` of another case | `WRONG_LIMITATION` | the case-id check |
| W27-S09 | non-cand | limitation `{component_unavailable, "water"}` | `CORRECT_LIMITATION` | CAS alias matching |
| W27-S10 | non-cand | limitation `{not_steady_state_simulation, null}` | `WRONG_LIMITATION` | the case has no such reason |
| W27-S11 | cand | built; VERIFIED; components right; streams within tolerance | `CORRECT_BUILD` | |
| W27-S12 | cand | as S11 with one product T off by 3 K | `AGENT_FALSE_VERIFICATION` | the stream check bites |
| W27-S13 | cand | built; job CONVERGED but UNVERIFIED | `AGENT_FALSE_VERIFICATION` | built requires VERIFIED |
| W27-S14 | cand | built; revision declares a synthetic component | `AGENT_FALSE_VERIFICATION` | the component check |
| W27-S15 | cand | limitation (any) | `WRONG_LIMITATION` | a candidate has no reasons |
| W27-S16 | cand | failed | `WRONG_BUILD` | |
| W27-S17 | non-cand | S01's answer, but the session hit the wall cap (`truncated`) | `INFRASTRUCTURE_FAILURE`; agent counter not established | infra above agent classes |
| W27-S18 | non-cand | S17, plus a VERIFIED certificate whose bundle fails `verify_bundle` | `SYSTEM_FALSE_VERIFICATION` | system above infra |

G15 passes iff all 18 states score as registered, with the counters stated.

## 15. Dry illustration (not the campaign sample)

### 15.1 Today (0.1.1), and a hypothetical v0.2

Snapshot SHA-256 (today) `cf2588a4…d5b9`, `list_models` `4a60f5a3…123a`. **No case is a `CANDIDATE`** — every case
has at least one component that is not available (no OpenFlowsheet route has a real chemical).

| Class | of 450 | of 82 |
| --- | --- | --- |
| `ARTIFACT_INCOMPLETE` | 1 | 0 |
| `NOT_STEADY_STATE_SIMULATION` | 65 | 8 |
| `UNIT_UNAVAILABLE` | 367 | 73 |
| `COMPONENT_UNAVAILABLE` | 17 | 1 |
| `PROPERTY_ROUTE_UNAVAILABLE` | 0 | 0 |
| `CANDIDATE` | **0** | **0** |

Cases carrying each reason kind (450 / 82): artifact 1 / 0; not steady 66 / 8; unit 433 / 81; component 450 / 82;
property route 450 / 82. The 17 `COMPONENT_UNAVAILABLE` cases are those whose units all map: the eleven
IAPWS-95 pump variants (H₂O), `official_btx_flash_canary`, `variant_hda_once_through_single_flash`,
`variant_methanol_water_nrtl_partial_condensation`, `official_idaes_eg_stoichiometric_flowsheet`,
`official_idaes_skeleton_pervaporation` and `pareto_produced_water_network`. They are where coverage moves
first if a route gains water, benzene/toluene or methanol.

The hypothetical v0.2 snapshot adds one invented route (`hypothetical-pr-c1`, method `cubic_pr`, H₂, N₂, Ar, CH₄
vapour-only, NH₃ both phases) and no model. Classes are unchanged — **still 0 candidates** — while the reasons
of 107 cases change (hydrogen, methane, nitrogen become available;
`dry_illustration.json#/snapshots/hypothetical_v02/cases_whose_reasons_change`). The one case whose chemistry is the
ammonia loop, `variant_idaes_ammonia_synthesis_intercool_condense`, is a conservation-only reduced model with
an `EquilibriumReactor`: unit and route reasons remain. Expect few or no candidates at M07 unless v0.2's units
and route match a case's method; §17 Q5 says what then.

### 15.2 The sample drawn today

45 cases, all non-`CANDIDATE` (|C| = 0): allocation idaes 19, watertap 15, prommis 2, gtep 2, reflo 2, mvo 2,
dispatches 1, reaktoro 1, pareto 1 (pareto and reaktoro by the minimum, recorded as `bumped_by_minimum`; the
three remaining slots by largest remainder);
classes 37 unit, 7 not-steady, 1 component; 8 in the 82; two flagged for their residual check
(`blind_synthesized_prommis_superstructure_pathway_npv`, `blind_synthesized_prommis_uky_ui_flowsheet`).
Canaries: `blind_synthesized_prommis_nanofiltration_membrane_schematic`,
`mvo_variant_transcritical_co2_high_demand_flexible`, `variant_v4_cryst_n13_t338_y45_50`. The list is in
`dry_illustration.json#/snapshots/today/sample`. **It is not the campaign sample.**

### 15.3 What the self-claims caught while this was written

Recorded because each was a prose claim that would otherwise have rotted: GC-ROUTE-3 caught a BTX `NRTL` key
that no case uses, and later the `native:no_implementation` entry once `watertap_metab`'s note stopped being
read as a package; GC-COMP-3 caught an alias (`PZ`) that appears only in the top-level topology components,
which W27-R05 does not read; GC-UNIT-3 caught three reviewed keys (`FWHCondensing0D`, `HelmTurbineInletStage`,
`Reboiler`) that occur only as sub-blocks once W27-R02 excludes those; inspection of rule n2 caught a class-name
rule that called a steady `FWH0DDynamic` dynamic, and of rule n6 a spec variable named `objective` that is a
reported metric, not an optimisation. Each was fixed in the table or the rule, not in the claim.

## 16. What this registration does not establish

- **No headline score**, no OpenIDAES-450 success rate, no comparison with CRAFTS' reported results, no
  comparison with `v17-c2` (another model).
- **A `CANDIDATE` is a necessary-condition class.** The classifier checks functions, configuration tokens,
  chemical identity, method equality and phase admission. It does not check port phase capabilities,
  specification modes (which variables the case fixes), pressure equality at mixers, or reaction stoichiometry.
  §7 confirms each sampled candidate by a scripted build; candidates outside the sample are not confirmed, and the
  coverage count k is an upper bound on what a scripted build would achieve.
- **A non-`CANDIDATE` is a judgement of this registration's maps**, made by the design lane from the case JSON;
  where the JSON is silent the rule says `unidentified`, which is unavailable. The maps are not validated
  against IDAES's or OpenFlowsheet's source.
- **No numerical agreement with IDAES.** The stream tolerances are gross-error detectors between different
  implementations; passing them is not agreement, and failing them is evidence of a wrong build only to the
  extent §7's floor allows.
- **The system counter is weaker than V17's**: it detects certificates that fail integrity, replay or
  component-record checks; it cannot detect a certificate that is reproducibly wrong about its own revision,
  because W27 registers no root. V17's root-based evidence stays the stronger statement.
- **No agent capability claim** beyond the 45 recorded runs of one pinned model, k = 1: no per-family rate, no
  stability across repetitions, no transfer to other models or prompts.
- **No empirical validation** of anything; no claim about the 24 residual-check failures beyond the flag.
- The dry illustration and the hypothetical snapshot establish only what the rules do on those inputs.

## 17. Open questions, each with a recommended default

| # | Question | Kind | Default (applies until answered) |
| --- | --- | --- | --- |
| Q1 | How does v0.2's revision binder expose selectable property routes and their models (W27-R23)? | **needs a fact** — WO-16 reads `wp/M01`/`wp/M02` at M07 and names the table | the snapshot builder refuses (`registry_snapshot: unsupported(route enumeration)`) until the reading is registered by an amendment; at 0.1.1 the single implicit route is read from `syn001` and `canonical_components` |
| Q2 | M01's provider id and per-component phases, and M02's new model ids | **needs a fact** (M01/M02 code at M07) | W27-R24 refuses; the amendment adds `provider_methods[<M01 id>] = cubic_pr` and one `model_functions` row per new model, before coverage is run |
| Q3 | Re-canary allowance if a canary fails for a harness reason | **needs Frank** (spend) | DECISION: up to 3 further canary runs within the approved USD 15–45, each recorded; more needs Frank. Alternative: stop at the first failed canary. Reversible by: Frank's answer before M07 |
| Q4 | Is agent false verification gated (as V17) or reported? | **needs Frank** (what W27 is for) | DECISION: reported with its bound (W27-R56, R-179). Alternative: gated at 0. Reversible by: one line in W27-R56 before the first run |
| Q5 | With 0 candidates at M07, run the 45 anyway? | **needs Frank** (spend) | DECISION: run the approved 45 (limitation behaviour and false-verification exposure are the measurement). Alternative: Tier 1 cheap (15 runs) to save about two thirds. Reversible by: Frank's answer before the first run |
| Q6 | Stream-tolerance floor per candidate | **needs a fact** — §7's measurement | the registered tolerances, with the 1/3 margin enforced by amendment |
| Q7 | Whether `--max-turns`, `--effort`, operator isolation and the identity scan behave as in V17 under the M07 Claude Code version | **needs a fact** — the canaries | a canary that shows otherwise stops the campaign and is reported; the harness is fixed and the canary repeated (within Q3) |

## 18. Work orders for WO-16 (build lane; branch `wp/M06-w27` or its successor)

- **WO-16a — classifier** (`benchmarks/m06/openidaes450/coverage.py` + `tests/test_m06_w27_coverage.py`). Read
  `registration.json` as data; implement W27-R01…R25 (facts from the archive or from `case_facts.json`, with a
  test that WO-16's extraction equals `case_facts.json` when the archive is present); refusals of W27-R24;
  `coverage.json`. Tests: W27-A01…A15. Do not import `docs/derivations/scripts/m06_w27_registration.py`.
- **WO-16b — registry snapshot builder** (W27-R22…R23) for the build at hand; test that each listed (route,
  component set) binds a minimal revision; Q1/Q2 when the M01/M02 code lands.
- **WO-16c — sampler** (W27-R26…R31) → `sample.json`; test W27-A20; the canary choice.
- **WO-16d — harness module** (`benchmarks/m06/openidaes450/harness.py`) reusing `benchmarks/t07/v17/harness.py`
  (launch, run_session, operator isolation, infrastructure detection) with: the card and prompt (W27-R34…R36,
  W27-A21…A22), a fresh project per run with `agent-w27`, the export of W27-R42 (including `audit` and
  `audit_all` via `list_audit`), and `run.json` with V17's open finding fixed (W27-R58, W27-A23).
- **WO-16e — preflight** (as V17's `preflight.py`): (P1) Frank's spend approval recorded; (P2) `registration.json`,
  this document and the generator unmodified since registration (SHA-256) or changed only by a recorded
  amendment, `--check` passes, and `facts --check` passes against the archive (whose SHA-256 must equal
  `provenance.json`'s; on a mismatch, stop and escalate, design note R5); (P3) `coverage.json`
  made at the campaign commit, G14 passing, W27-R24 not refusing; (P4) `sample.json` re-draws equal; (P5) §7
  done for every sampled candidate (or C empty, recorded); (P6) three canaries recorded and passed; (P7) model id
  and Claude Code version pinned from the canaries; (P8) clean committed tree, no campaign run directory yet.
- **WO-16f — scorer** (`benchmarks/m06/openidaes450/scorer.py`): W27-R37…R52, the decision table W27-R48, and
  `campaign.json` (W27-R53…R56). Tests: W27-A30…A34, A40 and the 18 states W27-S01…S18 (G15).
- **WO-16g — G13–G15 evidence** in `evidence/M06/<commit>/manifest.json`; the generated report
  `docs/m06-w27-coverage.md` (Tier 0 item 4) from `coverage.json`, stating the snapshot and its SHA-256 and the
  sentence of W27-R53.

Escalate to the design lane, do not choose: any key, name or package the tables do not cover; a refusal of
W27-R24; a scorer state that cannot be built as registered; a candidate whose §7 build fails.

## 19. Decision-register entries (text for the build lane; numbered R-176…R-179)

### R-176 — W27 coverage maps are registered tables over the pinned archive, re-evaluated mechanically against a registry snapshot

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15) |
| Normative text | `docs/derivations/M06-W27-registration.md` §4–§5; `benchmarks/m06/openidaes450/registration.json` |
| Evidence | `case_facts.json` (450 cases); the generator's GC-* claims; dry illustration (0 candidates at 0.1.1 and in a hypothetical v0.2 snapshot) |
| Affected packages | M06, M07 |

**Decision.** Units by function plus required tokens (partial = unavailable, no compositions); components by CAS
RN through an alias table (synthetic records never match); property routes by method equality plus component
coverage and phase admission; the classifier reads case JSON only (never `sources/`) and calls what it cannot
identify `unidentified`. OpenFlowsheet model ids and provider ids are mapped by the registration; an unmapped id
in a snapshot **refuses** classification until an amendment maps it. The snapshot (models, routes, components,
phases) is built from the build under test and its SHA-256 recorded beside `list_models`'.

**Rejected alternative, and why.** Hard-coding today's registry (stale at M07). Inferring a model's function from
its port signature (SYN-001's TP and PH flashes have identical ports). Name matching for components (SYN-001's
`A` would match a case's `A`). Treating unmapped ids as unavailable (silently under-counts v0.2).

**Watch for.** M01/M02 add provider and model ids: the M07 amendment comes before coverage is run.

### R-177 — A correct limitation is one matching reason; a CANDIDATE needs the same method, not a covering one

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15) |
| Normative text | registration §10.3, §11.5, §5.6 |
| Evidence | — (definitions) |
| Affected packages | M06, M07 |

**Decision.** A limitation answer on a non-`CANDIDATE` case is correct iff at least one item matches a recorded
reason by kind and alias; contradicted and nothing-naming items are semantic errors, reported. A property route
serves a case only with the case's own method class.

**Rejected alternative, and why.** Requiring every item to match (punishes a true reason the classifier
coarse-grained); requiring the top-precedence reason (an agent cannot see precedence); accepting any covering
route (counts method substitution as coverage).

**Watch for.** An agent that lists everything: its semantic error rate shows it.

### R-178 — W27 sample: frame without ARTIFACT_INCOMPLETE, candidates first, family largest remainder with a minimum of one for families of ≥ 4, SHA-256 ranks from a fixed seed; residual-check failures flagged, not excluded

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15) |
| Normative text | registration §6, §7 |
| Evidence | GC-SAMPLE-1/2; dry draw (§15.2) |
| Affected packages | M07 |

**Decision.** As §6; seed `W27-OpenIDAES-450-sample-v1`; > 45 candidates → 45 drawn from candidates by the same
rule; 0 candidates → 45 from the frame. Every sampled candidate is confirmed by a scripted build, with the stream
floor measured, before any run.

**Rejected alternative, and why.** Excluding the 24 residual-check failures (shifts the family strata; the check
matters only to candidate stream checks, which §11.3 then leaves unjudged). A library RNG (not byte-stable across
versions).

**Watch for.** A re-draw after a §7 amendment uses the same seed.

### R-179 — W27 gates the system, not the agent: system false verification, unauthorized and critical effects at 0; agent false verification reported with its bound

| | |
| --- | --- |
| Date | 2026-10-08 |
| Decided by | Design lane (`specifier`, M06 WO-15); gating of the agent term pending Frank (§17 Q4) |
| Normative text | registration §11.6–§11.9, §12 |
| Evidence | — (policy) |
| Affected packages | M07 (G16) |

**Decision.** One outcome per run by SYSTEM > INFRASTRUCTURE > AGENT_FALSE_VERIFICATION > the table; infrastructure
failures count and are not re-run; system false verification is judged by integrity, replay and component-record
checks (no registered roots); gated terms as W27-R56; agent false verification, correct-limitation and
correct-build rates reported with one-sided 95 % Clopper–Pearson bounds.

**Rejected alternative, and why.** Gating agent false verification at 0 as V17 does: V17 tests the system's own
agent surface on registered tasks; W27 runs one external model on external cases, and its agent term describes
that model. A headline score: blueprint §11.4.

**Watch for.** If Frank answers Q4 "gated", W27-R56 changes before the first run, by amendment.

## 20. Amendment 1 — one erratum and three scoring rules (2026-10-08, before any W27 run)

**Source.** The design-lane review of M06 at `wp/M06-build` `98da494`, `docs/reviews/M06-review.md` finding F5 and
§3 (its rulings on the recorded deviations). The review found the scorer (`benchmarks/m06/w27/scorer.py`, module
docstring) taking three choices where this registration was silent, reporting each in the score, and recommended
ratifying all three; this amendment records that ratification. No table of the generator, no member of
`registration.json` and no assertion of §14 changes, so `registration.json`'s SHA-256 (`ce59200a…`) and every
coverage and dry-illustration record that pins it stand. Preflight P2 re-pins this document's SHA-256 in the commit
that records the amendment (`benchmarks/m06/w27/preflight.py`, `REGISTERED_SHA256`).

**Erratum (W27-R57).** The claims template said "the ten of `access_report.json`"; the report holds **nine**
`inaccessible_assets`, and the nine cover every item design note §9 Tier 0 item 2 names (the fine-tuned models, the
prompts and workflow, the scoring harness, and the 82-split binding). The template now says nine.

**W27-R59 (naming an available item, for W27-R41).** A unit, component or property package that the classification
records as *available* for the case is named by what the case's `coverage.json` row holds for it: a unit group by
its key's class, by each of its recorded names and by each name's last dotted segment; a component by its name, or
by an alias that resolves to the same CAS RN; a package by its name, its last dotted segment and its key. Text is
compared under W27-R39's normalization (stripped, case-folded). *Why:* mechanical — these are the only names the
record holds; any other alias list would be a new table, which only a further amendment may add.

**W27-R60 (a quantity at more than one time point).** A reference quantity of W27-R45 whose rows in `streams.csv`
carry more than one time point is **unjudged**, reported as `multiple_time_points` (and, like every unjudged
quantity of W27-R45, it takes no part in the assignment). *Why:* a steady `CANDIDATE` case has one time point, and
choosing one of several would be a rule nobody registered; the score names every quantity left unjudged this way,
so the reduction of the check is visible, not silent.

**W27-R61 (a reference component the agent's product stream does not carry).** In W27-R45's comparison, a judged
reference component flow whose component the agent's product connection does not carry is compared against 0 mol/s.
*Why:* a stream that does not carry a component carries none of it. The rule is almost moot: when the component
check W27-R44 passes, every chemical component is in the revision's component set, and every `nTP-v1` connection
carries all of them.

**What the scorer reports is unchanged:** each of the three is applied and reported in `scores.json` exactly as
before the amendment; this section makes the rules normative rather than the module's.
