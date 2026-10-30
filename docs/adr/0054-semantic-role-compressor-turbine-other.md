# ADR 0054 — `semantic_role` gains `compressor`, `turbine` and `other`: an additive widening of the frozen revision schema

**Status:** **Proposed, 2026-10-29** (design lane, `specifier`, package V03, ruling round 1; manifest id `S13`). It
becomes **Accepted** when `evidence/S13/<C>/manifest.json` is `tested` at the release candidate C with V03.A28–A31
among its checks. The build lane marks it Accepted at WO-8, together with ADR 0053 (V03 spec §6).
**Author:** design lane (`specifier`), brief `docs/briefs/V03-rulings-1.md`.
**Normative text:** this ADR; `docs/derivations/V03-release-spec.md` §9.4 (Table R, the corpus) and V03.A28–A31.
**Change rule served:** `docs/interfaces-frozen.md` header (plan §2.2: a widening of a frozen schema needs a design-lane
ADR). Precedents for an additive enum widening without a version move: ADRs 0012, 0015, 0018, 0025.
**Register:** R-881, R-882.

## Context (measured at `wp/V03` = `98701cca`)

- `schemas/process-revision.schema.json` (frozen, plan §2.2) enumerates `instances[].semantic_role` as `feed`,
  `product_sink`, `mixer`, `heater`, `flash`, `splitter`, `reactor`, `separator`, `valve`, `pump`, `heat_exchanger`.
  S11 added `thermal.compressor` and `thermal.turbine` to the binder (`revision_binding.MODEL_SIGNATURES`, 30 model
  ids) with no role for them.
- Nine committed S11 cases write `"semantic_role": "other"`: `benchmarks/s11/gp/GP-C1`, `GP-C2`, `GP-C3`, `GP-M1`,
  `GP-M2` and `benchmarks/s11/thermal/TH-C1`, `TH-C2`, `TH-R1`, `TH-V1` (`.json`). That is 34 instances, and it
  includes feeds, sinks, heaters, flashes, valves and mixers, whose roles exist. Five test-side builders write the
  same value: `tests/test_s11_thermal_binding.py` `instance()` (a literal) and `tests/s11_gp_support.py`,
  `tests/test_s11_gp_binding.py`, `tests/test_s11_routing.py`, `tests/test_s11_gp_verifier.py` (`ROLES.get(model,
  "other")`). The two case generators (`tests/s11_gp_support.py`, `tests/s11_thermal_support.py`) emit the nine files.
- Through `application.validation.validate`, each of the nine gives `SCHEMA-01`
  `schema_invalid(/instances/<i>/semantic_role): 'other' is not one of [...]`. The other 71 of the 80 committed
  revision documents (V03 spec §9.4's corpus) give no `SCHEMA-01` failure. The S11 tests call the binder directly, so
  nothing ran the nine through the validator.
- No file under `src/` contains the text `semantic_role`. The binder, the solver and the verifier never read the role.
  It is part of a revision's canonical content (ADR 0002's closed list of excluded members does not name it), so it
  enters `document_sha256` and `revision_sha256`. The web shell shows it (M06 design §6.1, the instances table).
- The docs work (`wp/DOC`, `docs/DOC_DECISIONS.md` D3/Q1) labelled a turbine and a compressor `pump` to pass
  validation. That label misdescribes the unit.

## Decision

- **D1 — Three values, appended.** The enum gains `compressor`, `turbine` and `other`, in that order, after
  `heat_exchanger`. Nothing else in the schema changes. `$id` stays as it is: R-149's `$id` move is out of scope
  (R-185). `schema_version` stays `const 1`. The required list is unchanged.
- **D2 — The role stays descriptive.** No production code reads it, and this ADR adds no reader. A unit model the
  binder accepts has exactly one role, given by Table R (V03 spec §9.4: 30 model ids, image = the thirteen values other
  than `other`). `other` is for an instance whose unit none of the thirteen describes. Every bindable model has a
  listed role, so such an instance can only be a declared model the binder does not accept (P01's
  `artifact_ref: null`). Its document passes the schema stage and is refused at binding with its typed result,
  `unsupported` `model_unsupported(<id>)` (measured on GP-M1 with a model id `acme.membrane`), not with `SCHEMA-01`. `other` is never the role of a model in `MODEL_SIGNATURES`.
- **D3 — No `column`.** A column is a `separator`. S11 registered that (`docs/derivations/S11-design.md` §4.7.1), and
  the 16 committed column instances (`syn001.column`) use it.
- **D4 — Repository documents follow Table R; user documents follow the schema only.** Every committed revision
  document and every test-side builder takes each instance's role from Table R (V03.A30). The nine cases and the five
  builders are corrected that way (V03 spec §9.4, WO-3). The application validator gets no new check: user documents
  stay constrained by the schema alone.
- **D5 — A new unit model brings its role.** The change that adds a model id to `MODEL_SIGNATURES` adds its Table R
  row. The role is one of Table R's image, or a new value by an additive ADR like this one. V03.A30 (a) and (b) make an
  omission fail.

## Alternatives rejected

- *Amend ADR 0051.* WO-4 accepts ADR 0051 on S11's own evidence (R-876, V03 spec §6). An amendment would tie that
  acceptance to V03's evidence. ADR 0051's decisions about its units are not wrong. What is wrong is the frozen schema,
  which 0051 never touched, and test documents that write `other` even for units that have a role (GP-C1…C3 have no
  `thermal.*` unit at all). A change to a frozen schema is its own decision, with its own acceptance evidence.
- *Bump `schema_version` or move `$id`.* `schema_version` is `const 1`. A bump either invalidates every existing
  document or needs the const widened to an enum that no reader distinguishes. It also enters every revision's content
  hash, so every registered revision identity would move. An additive enum value keeps every existing document valid.
  The `$id` move is R-149's and touches every schema (R-185).
- *Add `column`.* That gives one role two names. The 16 registered column instances and S11 §4.7.1 already say
  `separator`.
- *A closed enum without `other`.* A unit outside the list could then be written only under a wrong listed role, which
  is exactly the docs workaround (a turbine labelled `pump`). A closed enum's one benefit is that it catches a shipped
  model with no role. Table R's test keeps that check for the repository (V03.A30), where it belongs, and leaves user
  documents with an honest value. Frank's standing directive is "as few limitations as possible" (default of N-9).
- *Keep the nine cases as `other` once `other` is valid.* No document digest would move. But 34 instances whose role
  is known would stay misdescribed, and the web shell shows them. The correction moves only the digests of nine
  documents that no committed record pins (searched at `98701cca`: neither file SHA-256 nor `document_sha256` occurs
  anywhere in the repository). *Erratum 2026-10-30 (V03 review F-V4): three W5c binding-structure pins in
  `tests/test_t07_w5c_signatures.py` carry `revision_sha256` of TH-C1, TH-R1 and GP-M1; re-pinned in `8c6ddb8a`
  (V03 spec §9.4).*
- *A role-against-model check in `validate`.* It would change validation reports and constrain user documents beyond
  the schema, for a field nothing reads.

## Affected requirements

Plan §2.2 (one frozen schema widened; no schema added or removed); blueprint §4.1 (ProcessRevision instances); S11
(the nine cases and five builders); M06 (the web shell shows the role; no code change); DOC (the examples' roles);
V03 (WO-3, WO-4, `required_adrs`).

## Migration impact

- `schemas/process-revision.schema.json`: three enum entries appended. The packaged copy is the `_data/schemas` link,
  so `tests/test_t08_w4_package_data.py`'s by-id digest test holds unchanged.
- Every existing document stays valid. A 0.2.0 reader refuses a document that uses a new value with `SCHEMA-01`. Such
  a document's `thermal.*` units cannot bind in 0.2.0 anyway.
- The nine cases are regenerated by their generators, and their bytes and `document_sha256` change. The five builders
  take Table R's role. The other 71 corpus documents are unchanged (measured).
- **Identity.** No number, `ProblemSpec`, binding outcome, residual or certificate verdict moves (V03.A31 shows the
  binder's outcome is the same under any role). What moves is the document SHA-256 and `revision_sha256` of the nine
  cases and of documents built by the five builders. So `scripts/s11_identity.py`'s family C keys for test nodes that
  bind them would differ in their document-digest component only. S11's G1 is S11's merge evidence against
  `8c34ecb0`. It is not re-judged at C, and it is not a proof of inertness across this change (V03 spec §9.4).
- The served MCP tool list does not contain the enum. The served digest stays D_3 = `455d01eb…` (measured at
  `98701cca`; `test_m07a_a37_the_chain_holds_on_the_served_list` in the default gate; V03.A23 at C).
- `docs/interfaces-frozen.md` gains this ADR's paragraph. V03 spec §2.2's `required_adrs` gains `0054` (25 entries),
  so `scripts/v0_3_gate.py`, `benchmarks/v03/registration.json` and `tests/test_v03_v0_3_gate.py`'s count follow
  (WO-3).
- `wp/DOC`: an example that labels `thermal.turbine` or `thermal.compressor` `pump` switches to `turbine` or
  `compressor`. Once both branches are on `main`, V03.A30 (c) fails otherwise.

## Acceptance evidence

V03.A28–A31 in the default gate at the merge into `main` and at C; S13's manifest at C lists them.
