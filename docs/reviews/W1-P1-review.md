# W1 P1 review: ADR 0060 (F1 extension registry) and ADR 0061 (F3 component data), with three rulings

Reviewer (design lane), 2026-11-05. Brief `docs/roadmap/brief-reviewer-W1-P1.md`. Reviewed the ADRs at `75e2b381`
against `brief-architect-W1-P1.md`, `target-architecture.md` §2.3, §2.4.4, §2.6, §3 F1/F3, §8 and
`foundation-rulings.md` Q2 (Amendment 2), Q7, Q9. I built and ran nothing. I checked the factual claims against the
code and data: `application/revision_binding.py:1575-1670`, `assessment/program.py:69-185`, `thermo/wilson_ig.py:149`,
`pyproject.toml:86-118`, F0's M9 set (`wp/F0:benchmarks/f0/corpus.json`, 35 paths), and all seven legacy YAML files,
which I tabulated with a short read-only Python script.

**Verdict.** Both ADRs are sound in structure. The identity rules move no legacy byte. The `MODEL_BASES` proof is an
exact set equality that a test can check. I recounted it from the code: 30 model ids, 54 pairs, and with
`syn001.cascade` 31 × 7 = 217, so 54 admitted and 163 refused (7 + 156). The "30 vs 31" in the brief is not a
discrepancy. `registry_sha256` and the data-lock SHA are deterministic across install orders and platforms, with the
two caveats in notes N2 and N4. No entry-point failure can change a core admission. Five findings must still be fixed
before the core freezes:
- an admission rule that admits a unit on a definition it does not accept;
- a work order that E01's closed contributor set makes unbuildable, which also leaves an R-931 flag gap in 0.5;
- an `implementation_sha256` and an attestation that ignore the descriptor payload;
- the identity rule giving two SHAs to one content;
- an exit test that is false in a source checkout.

**ADR 0060: accept after the listed fixes. ADR 0061: accept after the listed fixes and the ruling-1 table.**

## Findings, ranked

### Must fix

1. **ADR 0060 D5 step 2: a unit is admitted on a definition it does not accept.** Step 2 checks the unit's clauses
   against P_m ∪ P_d, and methods provide `conn:` tokens for every definition they support (D4 table). *Scenario:*
   definitions A and B; method M provides `conn:A`, `conn:B`; unit U requires `[["conn:A"]]`. `admit(U, M, B)` passes
   step 1 (`conn:B` ∈ P_m) and step 2 (`conn:A` ∈ P_m), so U is admitted on B. Legacy has one definition, so E-F1-1
   cannot see this. E-F1-9's brute-force oracle implements D5 and reproduces the error. Any v2 revision whose connection
   carries a second definition (F2) reaches it. *Fix:* in step 2, a `conn:` token is satisfied by P_d only, and every
   other token by P_m ∪ P_d. Add a fixed counterexample to E-F1-9: the case above, refused
   `capability_missing(U, M, conn:A)`.
2. **ADR 0060 D1/D8 step 6: E01 rejects every extension contributor, and nothing flags its results in 0.5.**
   `CONTRIBUTOR_ORDER = ("cost", "lca", "derived")` (`assessment/program.py:69`). `register_contributor` raises
   `ValueError` for any other name (`:173-177`), and for one of those names it overwrites the built-in.
   *Scenario:* F1-WO3 installs the dummy extension contributor that E-F1-12 requires. Step 6 either raises, or replaces
   `cost`. The claim "Does not amend ADR 0052" is false, and the WO needs a further design decision. In 0.5 the flag
   reaches only `list_capabilities` and `check_admission` (D9), so an assessment computed with an unreviewed
   contributor would carry no `extension_unreviewed`, against R-931. *Fix (needs a decision; I would take the first):*
   make `functional_contributor` extensions `preview` in 0.5, registered and listed but not passed to E01. Delete step
   6. E-F1-12 becomes "a dummy contributor is listed; E01's `_REGISTERED` is unchanged; E01 identity tests and F0
   pass". Risk 4 then reads: extension contributors reach E01 only by an ADR 0052 amendment (namespaced names, run
   only when the assessment document names them, the assessment report carrying the flag), in ADR-F8 or X01 rest. The
   alternative is to write that amendment now, inside F1-WO3.
3. **ADR 0060 D3/D9: `implementation_sha256` and attestations ignore the descriptor payload.** A v2 method's
   `implementation_sha256` is `self_sha256`, a hash of its modules only. Note §2.3.3 makes the descriptor carry
   behaviour (required record fields, phase models, vocabulary and derivative orders, domain rules). Every
   payload-only descriptor has `self_sha256 = sha256("[]")`. *Scenario:* editing a v2 method's declared domain or
   derivative orders, with the code untouched, leaves `implementation_sha256`, `data_sha256` and so every exact cache
   key unchanged. Stale entries are then served, and a replay bundle claims identity. An attestation on (id, version,
   `self_sha256`) also survives any payload edit, and for a `correlation_form` or `record_type` it survives every
   edit. *Fix:* D3: "a v2 method's `implementation_sha256` = `sha256(canonical_json([descriptor_sha256,
   self_sha256]))`". D9: an attestation matches (id, version, `descriptor_sha256`, `self_sha256`). Make the same
   change in ADR 0061 D10's parenthesis and in target-architecture edit 6.
4. **ADR 0061 D2: absent, `null`, `[]` and `{}` hash differently.** Canonical JSON distinguishes them, and the
   normaliser does not unify them. *Scenario:* an X11 fetcher emits `synonyms: []` (or `identifiers: {}`) in one
   library version and omits it in the next. The same record gets two SHAs. Every data lock that names it moves, and
   Q9's "a re-fetch that returns identical content is the same record" fails. This rule is frozen at W1's end.
   *Fix:* add step 2a, "remove every optional member whose value is `null`, `[]` or `{}`, recursively; required
   members keep their values". The derived `anchor_phase: null` is re-inserted by step 5, so normalisation stays
   idempotent. Add to E-F3-4: "absent, `null`, `[]` and `{}` optional members give one SHA".
5. **ADR 0061 E-F3-9 is false in a source checkout.** s07 holds id `Methanol`, name `Methanol`, CAS 67-56-1. s10 holds
   `CH3OH`, name `methanol`, and has no identifiers (R-706). A bare `methanol` misses `id:`, which is case-sensitive.
   Under `name:`, which is casefolded, it matches both records, in two classes, so the result is `component_ambiguous`.
   If `id:` were casefolded it would resolve to s07. Either way it is never the S10 record. Only a wheel, which has no
   s07 data, makes the assertion true. CI runs from a checkout. *Fix:* "in a checkout, `methanol` is
   `component_ambiguous`, ambiguity `identity`, two classes; `cas:67-56-1` resolves to s07; `id:CH3OH` resolves to
   s10".

### Should fix

6. **0060 E-F1-1: the universe is not pinned.** If the test restricts the right-hand side to the registered units, a
   unit missing from `legacy.json` drops out of both sides and the test still passes. *Fix:* assert the registered
   legacy unit ids = `set(MODEL_BASES) ∪ {syn001.cascade}`, the method ids = the seven, and ⋃`MODEL_BASES.values()` ⊆
   the seven. D6 should state that the generator enumerates units from `list_models` (`MODEL_SIGNATURES`, 30) plus the
   cascade.
7. **0060 D6/E-F1-4: `syn001.cascade` has no signature and no implementation set.** It is absent from
   `MODEL_SIGNATURES`, and `models/syn001/cascade.py` is not in M9. As written, E-F1-4 fails if the cascade's module is
   included. *Fix:* `signature: null` iff `bindable: false`; `implementation.modules: []` for the cascade. The E-F1-4
   union is taken over the 7 methods and 31 units, with the E01 contributors excluded. Also state that M9 paths carry a
   `src/` prefix and import-root paths do not.
8. **0060 D4/D7: one missing name quarantines a whole package.** A token in a registry-derived space (`conn`, `phase`,
   `attr`, `derived`, `kinetics`, `trial_set`, `x`) that names a descriptor that is not installed quarantines its
   package. *Scenario:* a unit requiring `conn:nTP-v1 | conn:acme.slurry` is quarantined unless `acme` is installed,
   so the CNF disjunction is useless across optional plugins. A broken `acme` then quarantines every package that
   mentions its names. *Fix:* static spaces (`vocab`, `flash`, `convention`, `legacy`) stay strict. Names in
   registry-derived spaces are checked by grammar only: an unregistered one is never satisfied, and admission carries
   the notice `capability_unresolved(<token>)`. The fixpoint text is then deleted.
9. **0060 D4: extensions may still require `legacy:` tokens.** An extension unit requiring `legacy:pr-c1-v1` is
   admitted on a v1 provider that no binder can run for it, since `MODEL_BUILDERS` is closed. *Fix:* "naming a
   `legacy:` token in `requires` or `provides`" → `reserved_capability`. Extend E-F1-2 to the unit side.
10. **0060 D8/D9: the usage recorder can lose the flag.** It fires on `resolve` or factory resolution. It misses a
    factory result that is cached across runs, a worker thread that does not inherit the context, and a concurrent run
    if the contexts are process-global. *Fix:* derive a run's extensions used from its documents: unit ids and
    versions, data-lock methods, definitions, record types read, contributors named. Look each up in the snapshot. Keep
    the recorder as a cross-check, a `ContextVar` that the run's executor copies into its workers.
11. **0060 D2/D8: limitation codes cannot be validated during build.** "a catalogued code" can only be checked by a
    catalogue lookup, which raises during build, and the extension's own entries are registered later, at step 5.
    *Fix:* validate against the core catalogue keys plus the package's own pre-validated message document, without a
    lookup.
12. **0060 D12 freezes a single-method `admit` before sides and method sets exist (needs a decision).** In §2.3.8 a
    unit evaluates each side with its own method set, and a stream may carry `mixed` and `solid` substreams. A
    unit-level `requires` against one method cannot express that. *Fix (my choice):* core = the token grammar,
    satisfaction and D5 for single-side units. ADR-F6 may add per-side `requires` and admission additively, and D12
    says so now.
13. **0060 D3: nothing guarantees `modules` is complete.** S1 counts "a module imported into such a hash set". *Fix:*
    for v2 built-ins, `registry_builtin.py --check` asserts that `modules` contains the intra-package import closure of
    the factory module (F0's AST scan). An edit to an undeclared helper then moves `implementation_sha256`.
14. **0061 D9: identity classes split one compound.** "By InChIKey, else CAS" puts l01's H2O (InChIKey and CAS) and
    s05/s07 H2O (CAS only) in different classes, so `H2O` reports `ambiguity: identity`. *Fix:* a class is a connected
    component of records sharing an InChIKey or a CAS.
15. **0061 D2 step 4: sort keys and dedupe are underspecified.** A `null` phase makes tuple sorting undefined. "Dedupe
    by (property, phase, indices)" silently drops a conflicting duplicate before step 6 can refuse it. The same holds
    for `parameter_set.components` and for NFC-colliding keys. *Fix:* sort by the canonical-JSON bytes of the key.
    Remove only canonically identical elements. A key collision is refused at step 6.
16. **0061 D12: identity-bearing text is left to the builder.** `transformation` is unstated. `meaning` and `note` are
    defined for "a merged entry" only. Entry `uncertainty` is unstated. Unmapped v1 keys (`rights.notes`, `role`,
    `dimension`) are unlisted. *Fix:* a closed mapping table, in which every v1 key is mapped or explicitly dropped and
    an unknown key fails index generation. `transformation` is `null` and `uncertainty` is `null` for every legacy
    entry. The note rule applies to every entry.
17. **0061 D4: `provenance.inputs` mixes file SHAs and record SHAs.** Legacy inputs are file SHAs; Q9.R5 fits will use
    record SHAs. The two are untagged, and the field is frozen at W1's end. *Fix:* `inputs: [{scheme: record | file,
    sha256, path: string | null}]`, with file SHAs over LF-normalised bytes.
18. **0061 code table: `molar_mass_inconsistent` is catalogued as a refusal, but Q7.A3 says it is "reported … in the
    validation class".** As a refusal it blocks E-F3-10's own case: `l01` H2 + O2 with `s10` H2O, which differ by
    7.8e-6 relative, a mix of atomic-weight conventions. *Fix:* make it a notice and list it under D7's findings.
    Element and charge imbalance stay refusals.
19. **0061 D11: rights rows are keyed by a source id that each record chooses (needs a decision).** A whole-source
    row (`record_sha256: null`) applies to every record with that key. *Scenario:* a user file with
    `defaults.source_id: legacy.m01` inherits `permitted`, and F8 then embeds it in a bundle. *Fix (my choice):* key
    whole-source rows by `source_sha256`, the SHA of the canonical `{id: entry}`. Reserve `legacy.` for the importer.
    Define "latest" as the highest insertion sequence, not `date`.
20. **0061 D8: what the legacy store holds depends on how the package is installed.** Only m01 and s10 components are
    package data (`pyproject.toml:96,108`). *Scenario:* a project bound to an l01 or s07 record in a checkout gets
    `data_unavailable` on a wheel. *Fix:* when a project registers or binds a legacy record, copy it into the project
    store.
21. **0061 D8: the path-length refusal happens "at store open".** If store open is part of project open, existing v1
    projects with deep paths stop opening on Windows. *Fix:* open the store lazily. Refuse only at the first store
    operation. Check the absolute resolved root.

### Notes

- **N1.** E-F1-5's committed `builtin-sha256.txt` changes with every edit to E01's directories or to a v2 built-in.
  Give it `--write/--check`.
- **N2.** The level grammar admits both `:01` and `:1`, and `s:n` alongside `s:n:0`. Equal descriptors then hash
  differently. Use `(0|[1-9][0-9]*)` and drop `:0` in normalisation.
- **N3.** Duplicate namespace: `extension_conflict(<kind>, <id>, <version>)` has nothing to name when no ids collide.
  Use `namespace_conflict(<namespace>)`. Before comparing, deduplicate one distribution that is seen twice on
  `sys.path`.
- **N4.** A wrong-case module path resolves on Windows and macOS but not on Linux, so quarantine becomes
  platform-dependent. Check the exact case.
- **N5.** Frozen or zip builds (X07a packaging) make the built-in self-hash raise at start.
- **N6.** D11 seed: replace "if R-880 …" with the actual row: `legacy.s10`, `permitted`, conditions "NOTICE Wilson
  block", basis R-880.
- **N7.** Write protocol:
  - ignore a failing `unlink(tmp)` once the target has been verified;
  - skip `.tmp-*` on rebuild;
  - write the object before the sqlite rows;
  - replace a corrupt target instead of failing forever.
- **N8.** Q7.A3's 4ε bound assumes M from a few rounded operations. Molecules from X11 with many element terms may trip
  it. This is for the specifier to watch, not an ADR fix.
- **N9.** E-F3-2's "`selectable_bases()`" clause covers only the profiles that are bases (not l01 or
  s10-verification).

## Rulings

**Ruling 1, ADR 0061 D12 provenance table: confirmed with four changes.** The principle: `derivation` describes the
step from the cited source to the stored value. Any derivation inside the source belongs in `note`. A value read from,
or evaluated with, a reference EOS has origin {measured}. Replace the table's rows as follows:

| Profile, field | origin | derivation | inputs |
| --- | --- | --- | --- |
| `syn001`, `s10-verification`: every field | {synthetic} | direct | — |
| `m01`, `l01`, `s10`: molar mass (formula, atomic weights) | {measured} | generated | — (17 `fit_inputs_unhashed`, pinned in the index) |
| `s05`, `s07`: molar mass (as published) | {measured} | direct | — |
| `m01`, `l01`: Tc, Pc, **acentric factor** (reference EOS, via chemicals HEOS) | {measured} | **direct** | — |
| `m01`, `l01`, `s10`: `ideal_gas_cp` (NASA TM-4513) | {computed} | direct | — |
| `m01`, `l01`: Δf h° (ATcT; **includes the 7 element zeros "by definition"**) | {computed, measured} | direct | — |
| `s10`: Δf h° (H(298.15 K) of the NASA-7 polynomial) | **{computed, measured}** | generated | **SHA of `benchmarks/s10/nasa7-low.json`** |
| `s10`: `vapour_pressure` (fit to CoolProp 8.0.0 reference-EOS P_sat) | {measured} | fitted | **SHA of `benchmarks/s10/saturation-points.json`** |
| `s10`: `wilson_lambda` (fit to Kurihara 1993) | {measured} | fitted | SHA of `benchmarks/s10/vle/kurihara1993_binaries.csv` |

The reasons for the four changes:
- **Acentric factor.** It is retrieved by the same path as Tc and Pc, and the project computes nothing. As
  `generated` it would raise 14 spurious findings.
- **s10 Δf h°.** NASA's a₆ carries the adopted thermochemical ΔfH°, so the origin is the same as ATcT's.
- **The two input files** exist in the repository, so their "if" is resolved.
- **Element zeros.** They are covered explicitly by the ATcT row.

Every `inputs` entry uses finding 17's tagged form. `transformation` is null for all legacy entries (finding 16).

**Ruling 2, anchor for records with no formation data and nothing phase-tagged: referred to the specifier.** The build
proceeds on null plus `anchor_undetermined`. Any value here amends Q2.R2, and the choice depends on facts in F4 (P2).
- **Why null is the right default.** It records exactly what the record says, which is nothing. It fails loudly. It is
  revertible by one regeneration of the legacy index before any released v2 document pins these SHAs.
- **Points against null, for the specifier:**
  - With null, Q2.R4's component datum never reaches s05 or s07, so no CoolProp or IAPWS-95 water record is usable on
    `ELEMENTAL-ref-v1`.
  - A wheel ships only the m01 and s10 component files.
  - The alternative is `ig` for `mol` basis with a notice `anchor_defaulted(<component>)`. It is harmless for inerts,
    and it fails loudly (`anchor_unavailable`) where a method cannot evaluate the ideal-gas state.
- **The fact that decides it:** whether F4's delegating IAPWS-95 and CoolProp compositions evaluate the ideal-gas state
  at (T°, P°).
- **Deadline:** before ADR-F4 is Accepted.
- **ADR text:** in risk 2, change "*Needs:* a specifier ruling" to "*Needs:* a specifier ruling before ADR-F4 is
  Accepted; changing the default regenerates the legacy index". D6 step 4 stands.

**Ruling 3, `assess_rights` as a fifth `Records` operation: accepted.** Rights must be settable on every transport
(C1). Folding the operation into `register_record` would mix assessment with identity (Q9.R3), and it would hand the
`draft` right, which agents hold by default, the power to vet data. There is no generic policy operation to fold it
into. Conditions, added to D13:
- an unknown `record_sha256` is `not_found`;
- a `source_id` that is not among that record's sources is `invalid_request`;
- each call writes one audit row;
- "latest" follows finding 19.

## Exact edits

**ADR 0060.**
- D5 step 2 and E-F1-9: finding 1.
- D1 `functional_contributor` row, D8 step 6, E-F1-12 and risk 4: finding 2.
- D3, D9 and target-architecture edit 6: finding 3.
- E-F1-1 and D6 enumeration: finding 6.
- D6 cascade payload and E-F1-4: finding 7.
- D4 spaces, D7 fixpoint deletion, and the notice in the code table: finding 8.
- D4 reserved rule and E-F1-2: finding 9.
- D8 usage recorder and D9 propagation: finding 10.
- D2 `limitations`: finding 11.
- D12: finding 12.
- D3 closure check: finding 13.
- N2 and N3 in D4 and D7.

**ADR 0061.**
- D2 step 2a and E-F3-4: finding 4.
- E-F3-9: finding 5.
- D9: finding 14.
- D2 step 4: finding 15.
- D12 mapping and the provenance table: finding 16 and ruling 1.
- D4 `inputs`: finding 17.
- Code table and D7: finding 18.
- D11: finding 19 and N6.
- D8: findings 20 and 21.
- Risk 2: ruling 2.
- D13: ruling 3.
- D10 parenthesis: finding 3.

## Not examined

- E-F1-11's 49 M1 revisions.
- CoolProp's per-fluid `describe()` (E-F1-3).
- The mechanics of the MCP digest and the R4-G3 re-take.
- MSG beyond §4.11.
- Whether the target-architecture edit lists are complete.
- X07a's packaging.
