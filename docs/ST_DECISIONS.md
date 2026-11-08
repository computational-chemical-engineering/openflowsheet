# ST build decisions (wp/ST)

Build-lane choices made while implementing `docs/design/ST-stream-table.md` (ADR 0068) and foundation
rulings Amendment 5. Each is revertible; the ones marked **Q** are batched for ST's single reviewer pass
(design-lane questions, with the default applied until ruled).

## WO-1 (core)

- **D1-1 (Q) — the per-component `h` form is summed with Python `sum`, as the verifier does.** Note §4.3
  and Q2.R11 (a) / Q2.A13 (a) write `H_p = Σ_c n_p,c h_c` "from 0.0 in provider order". The verifier's
  `checks.enthalpy_flow` (SYN-001's every non-degenerate stream, revision and legacy routes) forms it as
  `sum(flow * h_c for …)`, and since Python 3.12 `sum` of floats is Neumaier-compensated: on random
  SYN-001-sized terms a 0.0-loop differs from it in the last bit 22 % of the time (100 000 samples). G7
  requires bitwise agreement, so the report uses `sum(...)` (the verifier's arithmetic, D3's intent).
  `table._phase_enthalpy` (degenerate lifted splits only) keeps a 0.0-loop; those streams are not G7-bitwise
  cases. Ruling wanted: amend "from 0.0" to "as `checks.enthalpy_flow` sums it". Commit c79a99db.
- **D1-2 — the revision is parsed without its specifications.** `parse_revision` refuses a `free` or
  `guess` specification (`specification_role_unsupported`), so the legacy-route revisions of the corpus (the
  A02 runs) would be unreadable. The report reads no pin; it parses `{**revision, "specifications": []}`, as
  the legacy binder does (`application/binding.py:854`). Commit c79a99db.
- **D1-3 (Q) — legacy-route bundles: unit ids from the legacy binder's match.** On `legacy_eo` the state
  and certificate name the SYN-001 flowsheet's units (`U-HEAT.Q`, energy-row subject `U-HEAT`), not the
  revision's instances (`heater`). For a revision with a non-`fixed` specification the report maps each
  instance to its unit through `application.binding.bind_revision(...).graph.instance_ids` (the binder's own
  topology match; ~16 ms warm). Stream ids are the revision's on both routes. The note assumed every bundle
  is keyed by instance ids. Isolated in commit 1d3c954c.
- **D1-4 — Q1.A14 (b)'s probe stream.** "The first undeclared stream of a SYN-001 corpus revision" is
  `T05b:SC-1`'s S2, whose certificate carries an `independent_split` row `not_applicable /
  temperature_degenerate`; Q4.R12 (b) (ii) flags it at every state, so Q4.A15 (b) ("flag false") would fail
  by construction. The probe is the first such stream **without** a degeneracy row (`SYN-001-T06-NET02`, S3);
  Q4.A15 (c) adds the row test-locally. Test-only.
- **D1-5 — core errors.** `build`/`from_bundle` raise `StreamTableError(code, message, **detail)` with an
  existing `ApiError` code (`not_found`, `unsupported`, `internal_error`); WO-3 maps it to `ApplicationError`
  through MSG's member-detail helper. The core does not import `contract.py` (shared with MSG).
- **D1-6 (Q) — port objects carry an `absent` map.** §5's port object has `H_flow: q` and no `absent`, which
  breaks "null iff absent key" when a port's stream Ḣ is absent. Ports carry `absent` with
  `stream_enthalpy_absent(subject=U, streams=[…])`. WO-2's schema includes it.
- **D1-7 (Q) — phase `x`, `w` and the phase fractions are nullable.** §5 types them `number`, but Q4.R11 (c)
  and Q4.A14 (d) require `phase_fraction_mass` and `w` null with `value_not_finite` when a phase's mass
  underflows. The rulings win: arrays are given or null whole, the fractions are `q`. WO-2's schema follows.
- **D1-8 — `value_not_finite.subject`** is the stream id for stream, substream and phase quantities (the
  object holding the entry locates the phase; no rendered phase string), the unit id or `flowsheet` in the
  energy summary.
- **D1-9 — a non-finite minority-fraction quotient flags `flash_near_phase_boundary`** (the decision near it
  is not known to agree). Unreachable for a flash of a flowing stream in practice.
- **D1-10 — signed zeros in `n` and `m` are normalised to `+0.0` on every stream**, not only R0 (ADR 0001
  D1.5: the same state).
- **D1-11 — `judged_at` and `verification_status` sit at the document root** (§5's layout); `energy` holds
  `{convention, units, overall}`. §4.5's "beside them" is read as the root.
- **D1-12 — a non-finite `Tsat` blocks an R1 substream's properties like a refused one**, with
  `value_not_finite(subject=S, quantity=Tsat)`.
- **D1-13 — a unit without a quoted energy row has `closure` null with `energy_balance_undefined`** even when
  a stream Ḣ is also absent; `H_in`/`H_out` still carry `stream_enthalpy_absent`.
- **D1-14 — `from_bundle`'s `source`** has `job_id` and `bundle_id` null; its `not_found` detail uses MSG's
  field names (`bundle_id, member, members, job_id, run_outcome`) with nulls for what a directory lacks.

## Escalations (design lane)

- **E1 — G8 fails on `g8/T05b:SC-1` (gap 2016.0 W against 1.01e-3 W).** S2 is pure B at its boiling point
  downstream of a valve: a temperature-degenerate lifted split, whose Ḣ the verifier reads from the stored
  split (ADR 0012 D7). The report's raw TP flash (Q4.R12 (a)) lists LIQUID alone, so Ḣ(S2), the valve's
  closure and the envelope closure are 2016 W off (the vapour's latent heat). The stream **is** flagged
  (Q4.R12 (b) (ii), row `independent_split … temperature_degenerate`), as ruled, but G8 bounds the envelope by
  the row's tolerance. `T05b:SC-3` shows the same at its units (valve +2016 W, PH flash −2016 W) while its
  envelope cancels. The test asserts G8 as written and is `xfail(strict)`; a guard test pins the failing set
  to this one run. Fact for the ruling: note D4's reason for rejecting the carried lifted split ("needs the
  binding's `LiftedSplit` list, which `revision.json` does not carry") does not hold — `verify_revision`
  derives that list from the parsed revision (`orchestrator.splits.lifted_splits` over `view.instances`).
  Options: (a) G8 exempts an envelope with a stream flagged by (ii), Q4.R12 (c) already making the flag the
  only guard there; (b) a rule R1′ reading a temperature-degenerate lifted split from the state, as the
  verifier does. Default: neither applied; G8 reported FAIL.
- **Observation (no gate).** `g8/SYN-001-A02-360-liquid-guess`: the report's heater and flash closures are
  ±2.73e-3 W against rows of 1.01e-3 W (judged at the projection; the stored state's closure differs). G1
  bounds unit closures on TH-C1 only, so nothing fails; noted for the reviewer.

## Evidence for D1-1

G7 run (WO-1): 41 streams bitwise on G7's list; beyond it, 173 SYN-001 declared streams and 20 SYN-001
two-phase flashed streams the verifier reads by `checks.enthalpy_flow` without a snap are bitwise equal to it
too (0 mismatches) with Python `sum`.

## WO-2 (schema, without the registry entry)

- **D2-1 — "null iff a key of `absent`" is in the schema**, both directions, one `if`/`then` pair per
  nullable member (stream, substream, phase, port, unit, overall). The note calls it test-level; the WO-2 row
  lists "null without `absent`" among the fixtures the schema must reject, and JSON Schema can state it.
- **D2-2 — arrays are given or null whole**: `x`, `w` are `[number] | null` (§5 wrote `[q] | null`); the core
  never emits a null element.
- **D2-3 — §5 amended by D1-6 and D1-7**: ports carry `absent`; phase `x`, `w` are nullable arrays and the
  phase fractions are `q`.
- **D2-4 — fixtures.** Valid: WO-1 output of `g8/SYN-001-once-through` (syn001: declared, R3 two-phase and
  dormant streams), `m02/C1-FLASH-F1-M02-v1` (pr-c1-v1), `s11-th/TH-C1` (iapws95-v1), `s11-gp/GP-C1`
  (wilson-ig-v2). CoolProp is not installed here, so there is no coolprop-heos-v1 fixture and the core test
  asserts its `basis_unavailable` refusal instead. Invalid: `g8/T05b:DZ-7`'s document with one mutation each
  (phases keyed by the rendered family; a substream `h` null without an entry; a substream without
  `convention`; family `vapor`; an extra `name` in a phase id); the test checks each is rejected at the member
  it breaks.
- **D2-5 — registry entry pending.** `schemas/registry.json` is shared with `wp/MSG`; until WO-3 adds the
  entry, `tests/test_t08_w4_package_data.py` fails four tests (A48: the registry must equal the schema
  directory; 43 files against 42 entries). Expected; not loosened.

## WO-3 (operation), on `wp/MSG` merged (brief `docs/briefs/ST-build-WO3-6.md`)

- **D3-1…D3-5 — merge conflicts** (`git merge main` 56294e49, then `git merge wp/MSG` 22f64c65, no squash):
  D3-1 `benchmarks/t08/support_envelope.yaml` harvest: union, main's entries then MSG's. D3-2
  `tests/test_m07a_harvest.py` `HARVEST_SIZE` = base (68, 939, 120) + main's (7, 44, 6) + MSG's (2, 9, 3) =
  (77, 992, 129); the comment keeps both. D3-3 `docs/support-matrix.md` re-emitted by
  `scripts/t08_support_matrix.py --emit` (1121 items, 50 manifests; `--check` 0 problems). D3-4
  `tests/test_t08_w2_inventory.py` `SHIPPED_DATA` keeps both `_data/requirements.lock` (X05) and the
  catalogue files (MSG). D3-5 `docs/decision-register.md`: main's `R-942…R-949` (RP) kept, MSG's `R-942`/`R-943`
  appended unrenumbered — the id collision is MSG's to resolve at its merge (brief). Harvest and inventory
  tests: 25 passed.
- **D3-6 (Q) — a job without a `replay_bundle` output** is `not_found` "job <id> has no replay bundle" with
  detail `{job_id, run_outcome?}`: there is no bundle, so §6.1's `bundle_id, member, members` cannot be
  given. The `not_found` entry then renders its default summary ("Nothing named '<job>' exists"), which
  misreads the case. Ruling wanted: a `not_found` variant for it (MSG's catalogue), or a different detail.
- **D3-7 (Q) — surface chain link c_5** = (`ADR 0068`, `without_st`, `6705fb05…`) in `scripts/m07a_rc.py`.
  Its register column names the ADR: ADR 0068 is Proposed and its register entries are written on
  acceptance; with MSG's R-942/R-943 still colliding, an R-id picked here could collide again.
- **D3-8 — `_run_outcome(job_id)`** is factored out of `_missing_member` (same keys, same order) and serves
  both the member detail and the no-bundle refusal. MSG's FB-03b tests pass unchanged.
- **D3-9 — O2 resolved: no test pins a view's default depth at 4** (`test_t07_w5a_projection` reads the
  `DEFAULT_DEPTH` constant only); `get_stream_table` defaults to `STREAM_TABLE_DEPTH = 12` (= `MAX_DEPTH`).
- **D3-10 — refusal shapes.** `unsupported`: message the binder's code text (`basis_unavailable(<id>)`, as
  admission spells its unsupported codes), detail `{job_id, hint}`. `internal_error`: the core's message,
  detail `{job_id, bundle_id, reasons?}`. A missing member: message "bundle <id> has no <member>", detail
  `{job_id, run_outcome?, bundle_id, member, members, members_total?}` through MSG's helper.
- **D3-11 — `from_bundle(directory, *, source=None)`**: the operation passes `{job_id, bundle_id}`; a
  directory caller still gets nulls (D1-14).
- **D3-12 — G12/G13 are measured against the merge tree `22f64c65`** (main + MSG): `git diff main` includes
  MSG's own schema and code changes until MSG lands. Against it: schemas move only by `registry.json` +1 and
  the new file; no file under `verify/thermo/models/run/orchestrator` or `compiled.py` changes.

**Surface numbers (G12).** Served MCP list (19 tools): `eaff45852d75…0942eac` (MSG's D_4) →
`6705fb059ab8b09b6664537d4191728fe8241b3e8bad4de85801d2415effe2d4`; `without_st` of it is D_4 exactly. R4-G3: the
new row's snapshot is the `projection` `$def`'s, `951b77ea…` (= `get_artifact`'s); no existing snapshot moved.
`get_stream_table.md`: 1287 characters, SHA-256 `6f98ea4b62220c65e06328b15885f5df8eb5805432f283f7bfff0d2701e8f515`,
both reviews pending in `REVIEW.json`; `test_every_description_is_reviewed_by_both_lanes` stays red (3 open:
`explain` human, `get_stream_table` design-lane and human), as it is red on `wp/MSG` (1 open). A48
(`tests/test_t08_w4_package_data.py`) passes with the registry entry. F0 after WO-3: PASS (M1 50/50, M2 61/61,
M3 61/61, M4 61/61, M5 61/61, M6 85/85, M7 52/52, M8 105/105, M9 35/35).

## WO-4 (catalogue)

- **D4-1 (Q) — `energy_balance_undefined`'s gap capability is `"energy form:<model>"`**, not §6.4's
  `"energy_form:<model>"`: MSG's G4 jargon lint refuses a snake_case token in `gap.capability`
  (`lint.jargon("energy_form:<model>")` → `a snake_case token 'energy_form'`). `property:<property>` passes as
  written. Ruling wanted: accept the spelling, or quote the token.
- **D4-2 — the two notices go into a new `messages/catalogue/notices.yaml`** (family `notice`, MSG note §4.2.1;
  its page `docs-site/messages/notices.md` existed empty); the five refusals are appended to `refusals.yaml` in
  one ST block. `zero_flow` is new (MSG has only `zero_flow_conflict` and its siblings).
- **D4-3 — param types.** `stream` and `unit` are element types; `subject` (a stream, a unit or `flowsheet`),
  `phase` (a family, `VAPOR`…), `property`, `provider`, `status`, `quantity` and `model` are `text` (the phase
  vocabulary has no FLUID or SOLID; `element` would derive a revision path for a stream id); `streams` is a
  `list`. `status` is optional in `flash_failed` and `property_evaluation_failed`.
- **D4-4 — G15:** `stream_table.absent` reports each code to MSG's runtime audit (`audit.auditor.code`), as
  `Unbound` and `api_error` do; the session audit then fails on a code without an entry.
- **D4-5 — merge follow-up:** `limitations.yaml` re-synced (`msg_catalogue.py sync-limitations`; L41's text from
  main's X05) and the operations and limitations pages regenerated; `msg_catalogue.py check` PASS (373 entries,
  86 complete; G1, G2, G4 0; G5 clean).

## WO-5 (CLI)

- **D5-1 — the three forms and the paged assembly live in `application/stream_table_format.py`**, not in
  `cli.py`: the CLI module is thin by rule (a Python caller gets the same text, blueprint D15). Not in §9's
  file list.
- **D5-2 — the assembly resolves every elision, not only `/streams` and `/energy`.** §6.3 pages `/streams` when
  the view is `truncated`, but a projection cuts a nested array after 20 items without setting `truncated`
  (`projection._render`). `assemble` follows each `$elided` marker (an object past `depth`, a cut array, a
  size-capped view), pages arrays with `cursor`, and refuses `internal_error` on a differing `sha256`. Tested at
  `depth=1, limit=1` against the operation's document.
- **D5-3 — text layout choices §6.3 leaves open.** Header lines `key: value` (job and judged_at `-` when null);
  stream blocks headed `stream`; the energy table's unit and model columns 18 wide left-aligned, numbers 14
  wide right-aligned, the verifier column the quoted rows' results joined by `,`; `overall` reads `H_feeds` and
  `H_products` under `H_in`/`H_out`; footnote params as `key=value`, a list as `[a, b]`; a phase-less substream
  shows `-` in `phases`.
- **D5-4 — a refusal prints the `ApiError` document on stdout only with `--format json`** (as `explain --json`);
  the layered text is always on stderr. A directory's `not_found` leaves out its null detail members (D1-14).
- **D5-5 — the JSON golden is compared with `evaluator.package_version` set to the installed version**, the
  one member that moves with a release rather than with the run.
- **D5-6 — a CSV quantity cell is `repr(float(value))`**, so a document read back from canonical JSON (where
  `10000.0` is spelled `10000`) prints as the in-memory one does; the phase qualifier and ordinal print as text.

## WO-6 (docs)

- **D6-1 — the ADR 0019 pointer paragraph (Amendment 13) is written on `wp/ST`**, marked "in effect when ST
  merges": ADR 0068 says it is added on acceptance, and the branch merges only then.
- **D6-2 — pages:** `docs-site/guide/stream-table.md` (nav "User guide → Stream table", after Concepts), a
  `streams` section in `tutorials/cli.md` (the CLI reference), `streams` in `guide/interfaces.md`'s CLI row.
  The MCP description is WO-3's `get_stream_table.md` (both reviews pending). `mkdocs build --strict` was not
  run locally (it executes the notebooks); CI's site job does.
- **D6-3 — the `message_entry` fixtures re-taken** (`scripts/t07_schema_fixtures.py --write`): only
  `catalogue.sha256` moves, `e4f940cc…` → `8fa0c03e…`, from the L41 re-sync (D4-5) and the seven ST entries.

## Fix round (review `docs/reviews/ST-review.md`, brief `docs/briefs/ST-fix-round.md`)

- **M1 — rule R1′ (ruled, review M1).** `_decide`: R1, then R1′, R2, R3. The degeneracy rows are read once
  (`_Inputs.degenerate`); the heater-style split list is `orchestrator.splits.lifted_splits` over
  `view.instances` (no `staged`), filtered by the `vapor`+`liquid` port test, built only when a row exists. The
  Ḣ of an R1′ phase is accumulated from 0.0 (`_Decision.accumulate`). G8's strict xfail and its guard are removed
  (G8 passes); G7 compares R1′ streams bitwise against `table._phase_enthalpy(V) + (L)` at the stored state;
  G16 (c) now asserts R1′ (carried split, no flash call, not flagged) and the no-split case (test-local:
  `_heater_style_splits` patched to `{}`, since every corpus R3 stream has a split).
  Closures (`closure` vs quoted value, tol 1.01e-3 W, both `judged_at: projection`), before → after:
  `T05b:SC-1` envelope 2016.0 → 0.0, U-VLV 2016.0 → 0.0; `T05b:SC-3` envelope 3.64e-12 → 3.64e-12, U-VLV 2016.0
  → 0.0, U-PHF −2015.9999999999964 → 3.64e-12. Of the 44 served 0.3.0 documents exactly SC-1 and SC-3 move.
- **DECISION M1-1:** a flagged stream with no heater-style split that would reach R3 keeps `phase_source:
  "flash"` (the rule that applied) and `flash_near_phase_boundary: false` (nothing flashed, the review's reason
  for R1′). Alternative: a new source label, or the flag true. Reversible by: `_decide`'s last branch.
- **DECISION M1-2:** an R1′ phase whose provider returns mixture `h` takes `n_tot·h`, as the γ–φ verifier's
  `_phase_flow` does (D1-1: "summed as the verifier's helper of that form sums it"); the review's text names the
  per-component form only (`table._phase_enthalpy`). No corpus case reaches the mixture branch. Alternative:
  `property_not_provided`. Reversible by: `_Properties.enthalpy_flow`.
- **DECISION M1-3:** Q4.R12 (b) (ii) is dropped from `_near_boundary`: after R1′ no flagged stream reaches a
  flash, so it was dead. Note §4.2 and ADR D3 say so.
- **Fact (for the design lane):** a flagged *products-style* split's feed (`split.stream` = the drum's inlet)
  that is undeclared would take R1′'s no-split branch (`flash_failed`), although the verifier flashes that feed
  at its own state. No corpus or served case has one (all flagged streams: 4 R1′, 2 declared, 0 no-split).
- **S1 — G8u (per unit), `test_g8u_unit_agreement`, as the review specifies.** Corpus (52 runs): **every run
  is `judged_at: projection`**, so 0 units reach the bitwise branch and 0 the bounded branch; 146 whole-unit
  rows are recorded, max |closure − value|/tolerance **2.703** (`SYN-001-A02-360-liquid-guess` flash; heater
  2.703 likewise); 11 side rows not compared. G7 after M1: 41 bitwise (SC-1/SC-3 S2 now against
  `_phase_enthalpy`, before against `checks.enthalpy_flow` of a LIQUID-only flash); G8: 0 failures, max
  ratio 1.76e-4. `test_g8u_the_e1_units_close_within_their_rows` bounds SC-1/SC-3 explicitly (all ≤ 3.64e-12 W).
- **DECISION S1-1:** a unit is compared with its whole-unit row `energy_balance.<U>` only; `.hot`/`.cold` and
  the pump's `.work_relation` are other residuals than `(Q + W) − (H_out − H_in)`. Alternative: compare every
  row. Reversible by: `_g8u`'s id test.
- **S1 — A02-360 (2.73e-3 W against 1.01e-3 W): the projection.** At the stored state ST's `H_flow` equals
  `checks.enthalpy_flow` bitwise for every flowing stream of `SYN-001-A02-360-liquid-guess` (S3, the
  heater→flash stream, two-phase: 66173.21230169198 W both). So the heater's +2.7297e-3 W and the flash's
  −2.7297e-3 W are the stored state's own residual; the rows (1.46e-11, 3.64e-12) were judged at the projection
  x̃. Declared by `judged_at`; no ruling needed.
- **S2 — D3-6 ruled.** `not_found` gains `output: {type: text, optional: true}` and the variant `{has: [job_id,
  output]}` after the member variants, the review's wording verbatim; the no-bundle refusal's detail is
  `{job_id, output: "replay_bundle", run_outcome?}`. MSG's file: a one-hunk conflict is accepted at MSG's merge.
  `catalogue.sha256` `8fa0c03e…` → `81d3a6aa…` (message_entry fixtures re-taken; `api-errors.md` regenerated).
- **S3 — the three description edits, verbatim.** `get_stream_table.md` 1287 → 1486 characters, SHA-256
  `6f98ea4b…` → `76ac57f3a89b616157986b1b650a2793d1fa3271f705745c8c853249aa59fe1d`. `REVIEW.json`: design-lane
  `reviewed` (2026-11-08, citing `docs/reviews/ST-review.md` §Description), as MSG's 8c935831; the human review
  stays `pending`. Served MCP digest (c_5, `ST_SERVED_SHA256`) `6705fb05…` →
  `ebb4ca841958f26521f8239f40bb0dc67d59d0115dd391a69b87818db64fad22`; `without_st` still MSG's `eaff4585…`.
  `ST_FILE_SHA256` and `interfaces-frozen.md` re-pinned. Surface, chain, description, A48 tests: 178 passed;
  `test_every_description_is_reviewed_by_both_lanes` red with 2 open (`explain` and `get_stream_table` human).
- **S4 — the recorded route keys the units.** `from_bundle` reads `artifacts/solve-path.json` when the bundle
  has it and passes it to `build(…, solve_path=)`; `_unit_ids` maps through the legacy binder iff the recorded
  `solve_path` is `legacy_eo`, and falls back to the role test only without the file. Served 0.3.0 set: 47 of
  52 bundles record a route (11 `legacy_eo`, 36 `revision_eo`); the 44 documents are byte-identical before and
  after S4 (`document_sha256` per bundle). Tests: a `legacy_eo` bundle read with every role `fixed` and a
  `revision_eo` bundle with every role `free` give the bundle's document; the roles alone do not.
- **Text amendments (review Rulings), marked "from the ST review, 2026-11-08":** note §4.3 (D1-1: "summed as
  the verifier's helper of that form sums it"), §4.2 R0/R1 (D1-10, D1-12), §4.5 (D1-11, D1-13, D1-6's port
  entry), §5 (D1-6: ports carry `absent`; D1-7: phase `x`/`w` `[q]|null`, phase fractions `q`), §6.2 (D1-14,
  S4); ADR 0068 D4 (D1-1) and D5 (D1-6/7).
- **D4-1 ruled: plain prose.** `energy_balance_undefined`'s `gap.capability` is "an energy balance check for
  this unit's model" and `property_not_provided`'s "this property from the flowsheet's property basis" (static,
  as every other entry's). G5 asserts the exact text. `catalogue.sha256` `81d3a6aa…` →
  `7573d7ea42c41696f563bcb88cc89cb8d25df51619201086a09ff3ad19d4dd45` (fixtures re-taken; `refusals.md` regenerated).
