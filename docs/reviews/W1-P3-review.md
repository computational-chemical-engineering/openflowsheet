# W1 P3 review: ADR 0065 (F6 unit-model framework), ADR 0066 (F7 problem IR, run kinds), ADR 0067 (F8 identity, replay, evidence)

Reviewer (design lane), 2026-11-06. Brief `docs/roadmap/brief-reviewer-W1-P3.md`. Reviewed the three Proposed ADRs as
committed at `7bd2ad04`, against `brief-architect-W1-P3.md`, foundation rulings §16 Amendment 4 and the clauses it
inserted (Q1.R10, Q1.A13, Q2.R10, Q4.R9, Q5.R9–R11, Q5.A11–A13, Q9.R8, O-14…O-18), and `docs/derivations/F6-std-seed.md`.
I ran one thing: `f6_std_seed_reference.py --check` gave `PASS (107 claims)`. The generator imports only `mpmath` and
`s05_reference`, and nothing from OpenFlowsheet, so its expectations are independent. I re-derived MIX-1, VLV-1, PMP-1,
CMP-1, HTR-L and Q5.A13's Ĝ (cases (a) and (e)) by hand, and all agree. I checked these premises in code:
`compiled.py:35, 74–98` (the dataclass, the K01 no-default rule, the `RowAccumulation` literal), `serialize.py:43–61`
(an explicit field map, no `asdict`), `models/revision_flowsheet.py:925–945` (the v1 label is
`FSR1-<configuration>-<provider>-<impl>-<data>`), `run/replay.py:8–30, 240–272`, and the `implementation_sha256` feeders
(the thermo providers, so M9 does not cover `compiled.py`, `serialize.py` or `run/*`). I also checked ADR 0060 D8–D10,
ADR 0061 D10, ADR 0062 D7–D10 and ADR 0063 D2 and D7–D8.

**Verdict.** The layering holds. v1 and lowered runs keep every artifact, `differential_map` is invisible to every v1
digest, 0.3.0 bundles take the unchanged v1 replay path, and the three ADRs adopt the rulings faithfully, apart from the
merge gaps listed below. The architect's riskiest call is the code hashes in v2 `model_version`. It is sound, because it
follows R-047: v1 labels already carry the provider's `implementation_sha256` and `data_sha256`. Its replay consequence
needs one decision (S1). Six defects must be fixed before the freeze. Each is a bounded text edit, and I give the text
below:
- v2 `model_version` cannot see specifications or stoichiometry;
- control volumes have no manifest declaration;
- no construct lets a controller drive a duty;
- the routing rule assumes the first port is a vapour port;
- the `syn001` legs and E-F6-21 are unrunnable;
- E-F7-4 still asserts the example Amendment 4 refuted.

**ADR 0065: accept after the listed fixes. ADR 0066: accept after the listed fixes. ADR 0067: accept after the listed
fixes and the decision on S1.** No second architect pass is needed. M4 leaves one specifier item (the default is given),
which does not block the freeze.

## Findings, ranked

### Must fix

**M1. v2 `model_version` cannot see specification kinds, stoichiometry or other revision-level structure (ADR 0065 D3,
lines 106–129; departure 1).**
- *Where it comes from.* The departure drops the revision `content_hash` and states that "the declarations carry
  everything structural the revision contributes". They do not. Several revision-level choices change the residual
  without changing any id or declaration:
  - a Specification v2 target's kind or quantity (`{derived: T}` → `{derived: beta}` on the same stream under the same
    spec id);
  - a `reaction_sets` stoichiometric coefficient;
  - `phase_order_keys`;
  - the probe and sink wiring of energy and signal connections.
  v1 covers all of this through the label's `configuration_sha256` (`revision_flowsheet.py:925–945`: "the revision
  minus every pinned value… exactly what selects expressions without changing ids, ADR 0002 D2.7"). D3 leaves the v2
  `<label>` undefined.
- *Failure.* Edit only a reaction's `[p, q]`, or switch a T specification to a β specification. The ids, the
  declarations, the definitions and the data lock are all unchanged, so the two residual functions get the same
  `model_version`. Warm starts, sparsity reuse and every cache keyed on it then reuse the wrong structure. E-F6-17 does
  not catch this.
- *Fix.* Add a `sources` role `configuration`: id `""`, sha = `document_sha256` of the v2 revision with every pinned
  numeric value removed, which is v1's rule applied to v2 and keeps the departure's reason intact. Define the label as
  `FSR2-<configuration_sha256[:12]>`, within ADR 0002's 64-character label pattern. Extend E-F6-17 with "moves on a
  specification's target kind and on a stoichiometric coefficient; not on a specification value".

**M2. Control volumes are named but never declared (ADR 0065 D2, D4 line 133; ADR 0066 D2, D4 `HoldupDecl`, D6).**
- *The gap.* D4 gives control volumes an id namespace "declared in the manifest", and ADR 0066 D2 (c) puts a wall's
  `datum: {T_ref}` "in the manifest". D2's closed field table has no member for either. A `holdup_balance` row cannot
  name its volume, and `DynamicSpec.holdups` has no source.
- *Failure.* TX writes the first dynamic `std.*` variant against a frozen manifest that cannot say which volume a
  balance belongs to. It then needs an amendment of a frozen core table.
- *Fix (core grammar; F6 validates it, TX uses it).* Add the D2 row
  `control_volumes: [{id, side, holds: "side_definition", energy: bool, non_material: [{kind: <holdup_kind id>, datum?:
  {T_ref}}], zero_holdup_form: <form id> | null}]`.
- *Validation.* Every `holdup_balance` row's `holdup` names `{cv, kind, index}` of a declared volume. Volume ids and
  point ids are disjoint.
- *Other changes.* The declaration (D3) gains `control_volumes: [ids]`. ADR 0066 D4 says that `HoldupDecl` is built from
  this member.

**M3. No construct lets `std.pid` drive a heater duty, so E-F6-14 and Q5.A11 cannot be wired (ADR 0065 D10, lines
217–234; ADR 0062 D9).**
- *Why it cannot be wired.* ADR 0062 D9 offers a signal only these sinks: a signal port, and a `manipulable`
  *parameter*. `std.heater`'s duty is an energy-port variable fixed by the specification `Q − Q_spec = 0` (sheet §4.5;
  its only parameter is `pressure_drop`). A signal cannot end on an energy port (`signal_kind_mismatch`).
- *Failure.* The F6-WO7 engineer must invent the coupling. Either choice they could make is wrong:
  - a required `duty` parameter on every heater (D2: every parameter is required) breaks T mode;
  - a signal on an energy port breaks ADR 0062 D9.
- *Fix (core endpoint semantics).* Add a third signal sink, `{specification: <id>}`, mirroring ADR 0066 D5's time-input
  target. Its compilation: the specification row reads the signal symbol `~s` in place of its pinned value. A
  specification bound by a signal and by a time input is `parameter_binding_conflict`. ADR 0065 amends ADR 0062 D9
  additively.

**M4. D9 hard-wires "first port = vapour port" (ADR 0065 D9, lines 202–215; D2 `phase_routing`, line 89).**
- *The rules.* Rule (i) sends VAPOR to the first port and the LIQUID slots to the ports after it. Rule (ii) sends every
  active FLUID phase to the ports in density order.
- *Failure 1 (a seeded unit).* Run `std.flash` (`vapor`, `liquid`) on `cubic.pr-v1` with water and n-hexane at 300 K
  and 5 bar: two liquid-like FLUID phases and no vapour. The hexane-rich liquid leaves through `vapor`. The balances
  close, so the run is `VERIFIED` with a physically wrong outlet. The same feed on a `split` method sends both liquids
  to `liquid`. One process therefore routes differently by method family.
- *Failure 2.* A two-port liquid–liquid decanter on a `split` method (rule (i)) sends both liquids to the heavy port
  and nothing to the light port. Q4.R9 settles only the lone-phase case.
- *Fix, grammar (core, before the freeze).* `phase_routing` gains `vapor: <port> | null` beside `light_to_heavy`
  (liquid ports) and `solids`.
- *Fix, rule.*
  - VAPOR, or a lone `vapour_like` FLUID (Q4.R9), goes to `vapor`. When `vapor` is null it goes to the first liquid port.
  - LIQUID slots go over `light_to_heavy` by density.
  - With two or more active FLUID phases, the *default* (a specifier item for the next round) is: phases whose
    character is `vapour_like` go to `vapor`, and the rest go over `light_to_heavy` by density. A unit with `vapor: null`
    routes them all by density.
- *Tests.* E-F6-10 gains (e): failure 1 above as a regression case, and (f): a `split` decanter probe.

**M5. The `syn001` equivalence leg and E-F6-21 cannot run (ADR 0065 D17 line 330, E-F6-21 line 426; findings A4-a and
F6S-b).**
- *Why.* ADR 0063 composes no SYN-001 method (`0063:21–22`), so no `MaterialModel` exists for the syn001 basis. Step 1
  on syn001 cannot run, and neither can E-F6-21, whose `std.heater` would sit on the syn001 basis.
- *Fix.* Rule A4-a as below. Rebase E-F6-21 on a legacy source unit, with no phase-selecting point, of a basis ADR 0063
  composes and of a family that is not closed in 0.6. `thermal` closes, so a `thermal` unit would be refused
  `legacy_family_closed` in exactly this v2 revision. The candidate is a `c1` source on `composed.pr-c1-v1`. If no such
  unit exists, E-F6-21 runs on a test-only legacy-shaped unit registered on that basis.

**M6. E-F7-4 still asserts the example Amendment 4 refuted (ADR 0066 line 293; note §3 F7 exit lines 875–876).**
- *Where the edits fall short.* Edit 0066-2 corrects D7 but leaves the exit untouched. The exit still reads "PR liquid
  … carries `dae_index_near_singular`", which is false by Q5.R11 and Q5.A13 (e). Its "incompressible-liquid probe is
  refused" is also ambiguous: an incompressible liquid with α ≠ 0 is index 1, by Q5.A13 (e).
- *Failure.* The test as written fails against a correct implementation, or gets "fixed" by mis-scaling.
- *Fix.* Exact text in the 0066 list.

### Should fix

**S1. Replay step 5 makes every older v2 bundle `NOT_RUN` after any edit of a used built-in (ADR 0067 D5 step 5, line
100). Needs a decision.**
- *What happens.* `extensions_used` includes built-ins with their `self_sha256`, and step 5 requires equality. One edit
  to `std.heater`, or to a module in the compiler's import closure, therefore turns every earlier v2 bundle into
  `inspected_archived_results`/`NOT_RUN`: replay never reruns across releases.
- *What v1 does.* A provider edit moves the label and the rerun reports `MISMATCH` with its differences listed, so the
  replay still works as a regression check. Under step 5, v2 reference cases (X07b, TX transients) are uninformative
  from the first edit on.
- *My choice.* `extension_unavailable`, and a changed *non-built-in*, stay `NOT_RUN` as written. A changed built-in of
  the running distribution gives `compatible_reproduction`: a rerun under reason `extension_changed`, with the verdict
  from step 7. That verdict is `MISMATCH` by construction, but the R0 and float differences are listed. Either way, F8
  needs a re-record tool for registered v2 cases (add it to WO3).
- *The alternative.* Keep `NOT_RUN` and re-record every registered v2 case per release.

**S2. `extensions_used` placement is an unrecorded departure (ADR 0067 D2 line 56 vs ADR 0060 D9 line 347).**
- *The conflict.* ADR 0060 D9 puts "the run's extensions used" in `RunManifest.environment`, which is non-structural.
  ADR 0067 makes it a top-level structural R0 member.
- *Ruling.* Structural is the better choice: what ran is identity. Mark the change **[departure]** in D2 and amend ADR
  0060 D9's sentence (0060 list).

**S3. A coverage feed of `"basis"`, one per method, cannot serve pump, compressor, turbine and flash together (ADR 0065
D2 line 98, D16 lines 309–318).**
- *Why.* Each method gets one feed state. A pump needs a subcooled liquid, a compressor or turbine a superheated vapour,
  and the sheet's machine closure refuses the other phase (`inadmissible_phase`).
- *Failure.* On every `split` method, one machine's triple can never reach `VERIFIED`, so the matrix fails CI
  permanently.
- *Fix.* Bases entries carry named states (`liquid`, `vapour`, `two_phase`, `supercritical`). `coverage.feed` names one.
  A method without the named state is a CI failure, not a refusal.

**S4. The manifest cannot express the sheet's extensive specifications (ADR 0065 D2 line 84, D16 line 302).**
- *The gap.* `state_points.spec` kinds are "molar or specific". C8 and B-6 need (Ṡ, P) at the point's amounts.
- *Fix.* The kinds become `molar | specific | extensive`. D16's "(n, s_in, P_out)" becomes "(n, Ṡ_in, P_out), C8".

**S5. The dynamic scenario envelope (core) lacks what D4 needs (ADR 0066 D4 line 97, D5 line 130).**
- *The gap.* D4 refuses a steady unit's `holdup_balance` row "unless the scenario declares that instance quasi-steady".
  The scenario schema has no such member and does not say how an instance's dynamic variant is chosen.
- *Fix.* Add `quasi_steady: [instance…]` to the scenario.
- *Variant rule.* The binder takes the unique registered manifest with `variant_of` equal to the instance's model and
  `dynamic` in `modes`. Several candidates are refused `dynamic_variant_ambiguous(<instance>)`, unless the scenario
  names one in `variants: {<instance>: <unit id>}`.

**S6. Holdup ids omit the substream slot (ADR 0065 D4 line 142).**
- *The gap.* `<U>#<cv>~N[...]` gives "the carried index as connection n", but connection ids carry `@<substream>`
  (ADR 0062 D7). A volume holding water in two substreams collides.
- *Fix.* State that `N` and `A` carry the `@<sub>` slot exactly as connection `n` and `a` do. E-F2-5's generator
  includes a two-substream holdup.

**S7. The scope of retirement is undefined for lowered v2 revisions (ADR 0065 D17 lines 335–340). Needs a decision.**
- *The question.* "In a v2 revision the binder refuses" a closed family. A v1-expressible v2 revision is lowered and
  never meets the v2 binder.
- *Failure.* If lowering is also gated, then once `thermal` closes, ADR 0062's lift-and-lower fixtures on `thermal`
  cases fail. That would be an F2 exit regressing.
- *My choice.* Closure applies to v2-compiled revisions only, because a lowered run is a v1 run in every artifact
  (ADR 0062 D8). The alternative is to gate lowering too and re-base ADR 0062's lowering fixtures on open families.

**S8. Work orders do not carry the merged edits.**
- The sheet method `test.syn001-elemental` (sheet §2), on which F6S.A1–A9, A11, Q5.A11 and Q5.A12 all rest, has no
  work order.
- F7's D2.2 floors per event-function kind (edit 0066-3, `event_floor_unregistered`) have no work order.
- Q9.A9 is not in F8-WO7's acceptance.
- Q5.A13 is not in F7-WO3's, and Q1.A13 is not in F7-WO4's.
- Assignments are in the lists below.

**S9. E-F6-9 enumerates dormancy patterns only (ADR 0065 D7 lines 184–189, E-F6-9).**
- *Why that is not enough.* Under C5 the row swapped at dormancy depends on the specification mode. With an X-form
  specification it is the specification row; with a duty specification, `HTR-energy`.
- *Failure.* A per-unit block regular in duty mode can be singular in T mode, and the generator never builds it.
- *Fix.* Iterate dormancy patterns × each specification set in the unit's `coverage.specifications`.

**S10. `std.pid` without integral action is undefined in steady mode (ADR 0065 D10 line 224).**
- *The gap.* "With integral action it contributes…" says nothing about the other case. P-only control with a bias has
  a steady state (an offset) that the build lane would have to design.
- *Fix (default).* Steady mode requires integral action. Otherwise the binding is refused
  `mode_unsupported(steady, proportional_only)`, and a P-only law is TX's.

**S11. Merge window between F6 and F8-WO6 (ADR 0067 build order).**
- *The window.* F8-WO6 lands "after F6-WO4". If `wp/F6` merges first, then until it lands v2-compiled runs on `main`
  write v1-format bundles. Any fixture committed then has no data lock or registry snapshot.
- *Fix.* Make F8-WO6 a merge prerequisite of `wp/F6`, or refuse writing a bundle for a v2-compiled run
  (`construct_unavailable(bundle_v2, F8)`) until it lands.

### Notes

- **N1** (0065 D6 line 167). "Part of the declaration's row metadata, not of the structure document" leaves open
  whether raw-read sets enter `declaration_sha256`. They are code-determined and pinned by `self_sha256`, so say "not
  in the declaration document".
- **N2** (0066 D4 line 103). Two copies of the map exist: `DynamicSpec` and the metadata.
  - Say the metadata's copy is set from `DynamicSpec` at compile and is the one the integrator reads, and assert the two
    are equal.
  - The `= None` default departs from `compiled.py`'s K01 no-default rule (lines 78–82). It is acceptable because `None`
    means steady and dynamic problems are always v2-compiled, but record it.
- **N3** (0066 D7). The structural matching runs at build only. A zero-holdup form or a regime opening can make
  (A, Z) structurally deficient mid-run, and then rcond₁ = 0 and the LU fails. Re-run the matching per opening's active
  row set (cached per signature), with `dae_index_unsupported` at that event.
- **N4** (E-F7-2). G(x, +0) = F(x) is true by construction. Make it compare against the *steady variant's* residual on
  the shared rows at the steady solution.
- **N5** (E-F6-12).
  - A tolerance of 1e-14 relative to the result fails under cancellation. Use the sheet's (R) form: relative to the
    largest operand.
  - D12 needs `pow`'s rule: the exponent must be a `c` node unless the base is dimensionless.
- **N6** (E-F8-9). A 1-ulp perturbation need not change the adaptive step count, so the mutation control can be
  vacuous. Register a perturbation known to change it.
- **N7.** Risk 4 (compiler self-hash) is accepted on the R-047 precedent. Its cost to replay is S1's question.

## Rulings

**The eight departures.**
1. *Structure v2 without the revision `content_hash`.* **Accept, with M1.** Excluding pinned values matches v1's split
   between `model_version` and `constants_sha256`. The configuration half must come back as its own source.
2. *Adapter only for units without a phase-selecting point.* **Accept.** Carrying T05b's regimes into ADR 0064's
   controller would be a second contract inside the first, and nothing in the corpus needs it. E-F6-21 is rebased (M5).
3. *F6 seeds only `std.pid`.* **Accept.** F6's exit needs only the PI loop. The other laws are defined by their
   dynamics, which TX owns.
4. *Time inputs in a dynamic scenario document.* **Accept, with S5.** One steady revision keeps one `content_hash`
   across disturbance studies, and the scenario's own SHA identifies it in F8's `documents`.
5. *`differential_map` hashed in structure v2, dynamic only.* **Accept.** Equal rows and columns with a different
   pairing are a different DAE. The map is absent, not empty, for steady problems, so no v1 digest sees it. The
   metadata serialiser is an explicit map (`serialize.py:43–61`) and no `asdict` touches the metadata.
6. *ADR 0060 D9 narrowed (no notices in the certificate).* **Accept.** It keeps certificate bytes independent of review
   status, which E-F7-8's byte equality with `solve` needs. Edit ADR 0060 D9's sentence (0060 list).
7. *ADR 0052's extension-contributor amendment goes to X01 rest under D11's constraints.* **Accept.** E01's dispatch
   and identity are E01's, and D11's four constraints bind the later ADR.
8. *ADR 0063 D7 amended additively (`entries_read`).* **Accept.** Write the hook into ADR 0063 D7 itself, beside B-6,
   so that F4-WO4 builds it. ADR 0067 D6 then only cites it.

**The specifier's three findings.**
- **A4-a / F6S-b (SYN-001 composition).** ADR 0065 owns it (D17, E-F6-5, E-F6-21; F6-WO6).
  - In 0.6 the `syn001` leg prints `equivalence_pending(syn001)`.
  - F6S.A1–A11 on the sheet method are the analytic evidence for the `std.*` rows on SYN-001's potentials.
  - A delegating `composed.syn001-v1` is a later additive ADR 0063 amendment. It needs a specifier mapping of SYN-001's
    `lnK` onto `lnphi`, and it belongs to the package that retires `syn001`.
- **A4-b (D2.4 band at a zero threshold).** ADR 0067 owns it, as an amendment of ADR 0007 D2.4 (0067 already amends
  ADR 0007 D1 and D4).
  - The text: "where q* = 0, near threshold iff |q| ≤ 10 τ, τ in q's units: the kind's D2.2 floor or the clause's
    stated tolerance."
  - Q5.R10, Q9.R8 and Q1.R10 are its instances. No new work order: each consumer implements its instance.
- **F6S-a (a refused stream point).** ADR 0065 owns it.
  - Add a verifier check `stream_point`: for every flowing material connection, its PH point under the producer side's
    method is evaluated, and a refusal fails the check (`stream_point_refused(<connection>)`). Such a run is never
    `VERIFIED`.
  - It is built in F6-WO4 and tested with a probe whose outlet ĥ lies outside the method's domain.

**Other departures found.**
- The v1 label's configuration half was dropped (M1).
- `extensions_used` placement (S2).
- The `= None` metadata default against K01's rule (N2).
- None of these is a ruling change. Each needs only recording or the fix given.

## Consolidated edits (the specifier's 18 merged; ✱ = specifier edit, adopted as written unless noted)

### ADR 0065
1. ✱0065-4, header: add Q4.R9, Q5.R9, Q5.R10, Q2.A12 (b), (c), Q4.A12, Q5.A11, Q5.A12 and the sheet. Add to the
   Amends list "ADR 0062 D9: a `{specification}` signal sink (D10)".
2. D2 table:
   - add `control_volumes` (M2);
   - `state_points.spec` kind gains `extensive` (S4);
   - `phase_routing` gains `vapor: <port> | null` (M4);
   - `coverage.feed` takes a named state (S3).
   Validation, append: "out_min ≤ out_max for `std.pid`" (✱0065-2); "every `holdup_balance` row names a declared volume;
   volume ids and point ids disjoint" (M2). E-F6-2 gains one fixture per new rule.
3. D3:
   - `sources` gains the role `configuration`, and the label is `FSR2-<configuration_sha256[:12]>` (M1).
   - The declaration gains `control_volumes: [ids]`.
   - Append: "raw-read sets are not in the declaration document" (N1).
4. D4: `N` and `A` carry `@<sub>` as connection `n` and `a` do (S6); `#<cv>` names a `control_volumes` id.
5. D6: ✱B-1 (C4: dormant points are not evaluated; their labels are `+0.0` with derivative `+0.0`; point-level T and P
   are readable at any slot of a non-dormant point).
6. D7: ✱B-2 (labels may target a unit-owned ĥ; C5, one label per dormant ĥ).
7. D8: ✱B-3.
8. D9: ✱0065-1 as written for (iii) and for the last sentence. Then replace (i)–(ii)'s port assignment with M4's rule
   (`vapor` port; LIQUID slots over `light_to_heavy`; ≥ 2 FLUID phases by the default stated, specifier item SQ-F6-5).
9. D10:
   - ✱0065-2 for the closure.
   - After "parameter sink …", add "A specification sink `{specification: <id>}` makes that specification's row read the
     signal's `~s` in place of its pinned value; bound also by a time input: `parameter_binding_conflict`" (M3).
   - Append "steady mode requires integral action, else `mode_unsupported(steady, proportional_only)`" (S10).
10. D11: ✱0065-3, then append F6S-a's `stream_point` check (Rulings).
11. D16:
    - ✱B-4.
    - "(n, s_in, P_out)" → "(n, Ṡ_in, P_out) (C8)".
    - Append: "the sheet method `test.syn001-elemental` (sheet §2) is a test-only composition registered only in test
      registries".
12. D17:
    - Step 1: "on the `syn001` …" → "on the Wilson, IAPWS-95 and CoolProp bases; the `syn001` leg is
      `equivalence_pending(syn001)` until a delegating SYN-001 composition exists (A4-a)".
    - Retirement: "a closed family is refused in v2-compiled revisions; lowered revisions are v1 runs and unaffected"
      (S7, per the decision).
13. Exits:
    - ✱B-5 (F6S.A1–A11 into F6-WO5; E-F6-9 checks §4.10's table).
    - E-F6-9 iterates dormancy patterns × `coverage.specifications` (S9).
    - E-F6-10 cites Q4.A12 (✱0065-1) and gains (e) PR water/hexane LLE in `std.flash` → hexane-rich to `liquid`, and
      (f) a `split` decanter (M4).
    - E-F6-14 cites Q5.A11 and uses the specification sink.
    - E-F6-16 adds Q2.A12 (b), (c) (✱0065-4).
    - E-F6-17 adds M1's two cases.
    - E-F6-18 cites Q5.A12 (✱0065-3).
    - E-F6-21 is rebased (M5).
    - New E-F6-22: `stream_point` fails on a refused stream point.
14. Work orders:
    - F6-WO4 adds `tests/f6/sheet_method.py` and the `stream_point` check (E-F6-22).
    - F6-WO5 acceptance adds F6S.A1–A11.
    - F6-WO7 adds the specification sink and Q5.A11 and Q5.A12.
15. Codes: `stream_point_refused`, `dynamic_variant_ambiguous` (reserved for TX).
16. Risk 1 "resolved (the sheet)". Specifier questions: SQ-F6-1, -3, -4 "ruled (Amendment 4)", SQ-F6-2 "ruled (the
    sheet)" (✱0065-4). Add SQ-F6-5 (M4's ≥ 2 FLUID default).

### ADR 0066
1. Header, adopts verbatim: add Q1.R10, Q1.A13, Q5.R11, Q5.A13.
2. D2 (c) and D4: "`HoldupDecl` is built from ADR 0065 D2's `control_volumes`; a wall's `datum` is declared there" (M2).
3. D4: append "the metadata's map is the one set from `DynamicSpec` at compile; the integrator reads it; the default
   `None` (steady) is a recorded exception to K01's no-default rule" (N2).
4. D5:
   - ✱0066-1.
   - The scenario envelope gains `quasi_steady: [instance…]` and `variants?: {<instance>: <unit id>}`, plus S5's
     selection rule.
5. D7: ✱0066-2. Optionally append N3's per-opening matching.
6. D16: ✱0066-3 (τ_loc). Risk 1: "TX re-runs Q1.A11, A12 and A13 on its BDF".
7. E-F7-4 → "An index-1 probe is accepted; Q5.A13 (a)–(f): (f) α ≡ κ ≡ 0 refused `dae_index_unsupported` naming the
   volume row; (c), (d) carry `dae_index_near_singular`; (e) (thermally expanding, κ ≡ 0) and a `cubic.pr-v1` liquid are
   regular" (M6).
8. Exits: add Q1.A13 and Q5.A13 (✱0066-3). E-F7-2 per N4.
9. Work orders:
   - F7-WO2 adds the D2.2 floor per event-function kind (`event_floor_unregistered`).
   - F7-WO3 acceptance adds Q5.A13.
   - F7-WO4 acceptance adds Q1.A13.
10. Codes and questions: `simultaneous_event_conflict`, `event_chattering`, `event_floor_unregistered` (✱0066-3).
    SQ-F7-1 and -2 "ruled (Amendment 4)".

### ADR 0067
1. Header, adopts verbatim: add Q9.R8, Q9.A9. Amends: add "ADR 0007 D2.4: the additive band at q* = 0 (A4-b)", with the
   text in Rulings.
2. D2: mark `extensions_used` **[departure from ADR 0060 D9]**: structural, top level (S2).
3. D5 step 5: per S1's decision. Default: a changed built-in → `compatible_reproduction`, rerun, reason
   `extension_changed`. F8-WO3 adds a re-record tool for registered v2 cases.
4. D6, F4 hook: "specified in ADR 0063 D7" (departure 8).
5. D8: ✱0067-1. F8-WO7 acceptance: E-F8-9 and Q9.A9. SQ-F8-1 "ruled, default changed (Amendment 4)".
6. Build order: F8-WO6 is a merge prerequisite of `wp/F6` (S11).

### ADR 0063 (cross-ADR)
- ✱0063-1, ✱0063-2, ✱0063-3.
- ✱B-6 (state-point specifications may carry `enthalpy_flow`, `entropy_flow` at the point's amounts; the isentropic
  reference uses (Ṡ, P)).
- D7 gains `entries_read(point_id) -> tuple[EntryRead, ...]` as ADR 0067 D6 defines it (departure 8); F4-WO4 builds it.

### ADR 0062 (cross-ADR)
- ✱B-7 (D10: a `{derived: X, stream: S}` target on an `h_mass` connection compiles by C3).
- D9: the endpoint list gains `{specification: <id>}` (signal sink only), by ADR 0065 D10 (M3).

### ADR 0060 (cross-ADR)
- D9's propagation sentence → "From F8: `RunManifest.environment` carries the snapshot (D10); the run's extensions used
  are a structural member of `RunManifest` (ADR 0067 D2); the run's evidence report, not the certificate, carries the
  notices (ADR 0067 D6)."

### Note (`W1-P3-note-edits.md`, for the orchestrator)
- §3 F7 exit (`target-architecture.md:875–876`): the same replacement as E-F7-4.
- §2.4 routing: M4's `vapor` port.
- §2.4 identity: M1's `configuration` source.

## Not examined

- `target-architecture.md` beyond lines 566 and 875–876.
- The 30 note edits, beyond a grep.
- ADR 0005, 0008, 0012, 0019, 0020, 0034, 0052 and 0054, beyond what the P3 ADRs quote.
- `00-core-inventory.md` and the register.
- Q1.R7–R9 and A10–A12, beyond their adoption.
- The generator's code, beyond its imports and its `--check`.
- The TX, X25 and X26 designs.
- No schema draft exists to check: the ADRs give their schemas inline.
