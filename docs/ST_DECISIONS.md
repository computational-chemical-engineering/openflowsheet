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
