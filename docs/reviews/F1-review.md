# F1 review: the extension registry, with the batched design-lane rulings

Reviewer (design lane), 2026-11-11. Reviewed `wp/F1` at `922eef54` (range `main..HEAD`, `main` = `b6cdf552` = v0.4.0)
against ADR 0060 (Proposed; core frozen by R-941), `docs/roadmap/target-architecture.md` §3 F1 and the build log
`docs/F1_DECISIONS.md` (W1-1 to W4b-8). WO1 to WO4b are built; WO5 (the real-built-ins constant, CI, manifest) is not.
This is the package's single reviewer pass. Runs on SMM-TR09, in the worktree:

- `corpus_identity.py --check`: `F0 PASS: M1 50/50, M2 61/61, M3 61/61, M4 NOT JUDGED, M5 61/61, M6 70/70, M7 52/52,
  M8 105/105, M9 35/35`.
- `registry_builtin.py --check`: clean, 42 descriptors in 2 tables, `registry_sha256 f4722624…`.
- The five `tests/test_f1_*.py` files: 243 passed in 43 s.
- The 19 existing test files the branch edits, plus `test_v03_semantic_roles.py`: 655 passed, 1 failed. The failure is
  `test_every_description_is_reviewed_by_both_lanes`, red by design until both reviews of the two new texts are recorded
  (W4a-11, the X04 precedent).

**Verdict.** The build matches D1 to D12 closely, and F0 identity is intact. The exit tests E-F1-1 to E-F1-4 and E-F1-6
to E-F1-12 hold. Each falsifies what it claims, with two gaps: E-F1-4 checks only the union of the module sets, not which
descriptor holds which module (SF-6), and E-F1-11 cannot see the binder's verdict on 12 of the 50 revisions (ruled
below). E-F1-5 holds on the synthetic built-ins; the real constant is WO5's. The agent surface is sound. Link c_9's
chain proof is correct and has its own left-in-place control. No check was relaxed (§ "Edited checks"). One must-fix
item: the ADR text must absorb the build's departures from frozen core text before Frank accepts it. The should-fix
items are local and small. F1 may proceed to WO5. It may not merge or be marked `tested` until MF-1 is applied, the
two description reviews are recorded, and WO5 is green.

## Findings, ranked

1. **MF-1. Frozen core text and the build disagree, with no amendment.** Under R-941 the D6 legacy payloads and D5's
   refusal wording are core. Two build decisions change them: W2-2 adds the member `per_component` to D6's closed
   legacy payload, and W4a-13 reads D5's "`gap.capability` = its third parameter" (ADR line 193, code table line 491)
   as "the token is `params.capability`". Two further decisions add to or correct ADR text: `factory_unavailable` (W3-10)
   is a code missing from the ADR's code table, and E-F1-11's "(49)" (line 479) should read 50. *Scenario:* Frank
   accepts ADR 0060 as written, and the frozen contract then contradicts the shipped payload schema and the shipped
   catalogue entry. *Remedy:* before acceptance, add a section "Build findings applied (F1 review)" to ADR 0060 and
   edit the text in place, as the rulings below specify: D6 (`per_component`), D5 and the code table (gap reading,
   `factory_unavailable`), D4 (the convention source, ruling W1-8), D8 (the v1 version rule, W3-12), and E-F1-11
   (50 revisions; the 38/12 split). Add one register entry. No code moves.
2. **SF-1. The Python transport does not validate its arguments.** `LocalApplication.list_capabilities`
   (`application/local.py:1759`) does not call `_check_limit`, although every other paged method does
   (`local.py:1300`). I measured: `limit=0` raises `IndexError` (`capabilities.py:120`, `page[-1]`); `limit=10000`
   returns everything; `kind="bogus"` returns an empty page; and `check_admission(pair={"unit": 5, …})` raises
   `AttributeError` in `closest`. Over `dispatch`, all four are typed refusals, so rule C1's parity fails on the direct
   protocol call. *Remedy:* call `self._check_limit(limit, MAX_PAGE, name)`, and refuse an unknown kind and non-string
   ids as `invalid_request` with a pointer (or validate against the row's request schema first). Add four tests.
3. **SF-2. A broken extension can still be fatal, against D7's "never fatal".** `selfhash.file_sha`
   (`registry/selfhash.py:48`) lets `OSError` escape. I measured: a package whose module file is unreadable (mode 000)
   makes `Registry.build` raise `PermissionError`. In the process registry, the failure lands in `default_registry()`,
   and that runs inside the catalogue's first lookup (`messages/catalogue.py`, `_frozen_entries`). Every message render
   then raises, along with `LocalApplication.open` and `cli.main`. `_add_package` (`registry/__init__.py:329`) has no
   catch-all, and `entry_points()` (`discovery.py:117-121`) reads every distribution's metadata unguarded. *Remedy:*
   map `OSError` to `SelfHashUnavailableError`. Wrap each package's `_add_package` and each distribution's metadata
   read so that an unexpected exception quarantines that package as `extension_invalid(<entry point>, "")`, with the
   class logged as `discover` does. Add a test with the mode-000 file.
4. **SF-3. `dependency_missing` cannot fire for the only built-ins that have an extra.** `Registry.factory`
   (`registry/__init__.py:543`) refuses only when importing the factory module fails. `coolprop-heos-v1`'s factory
   module is `revision_binding`, which imports CoolProp lazily (`revision_binding.py:1900`). Without CoolProp,
   `factory("property_method", "coolprop-heos-v1")` therefore returns `basis_provider`, and the failure appears later,
   untyped. The same mapping turns *any* `ImportError` into `dependency_missing` when `pip_extra` is set. *Remedy:* when
   `pip_extra` is set, check that the extra's requirements, read from the declaring distribution's metadata, are
   installed before returning; map `ImportError` only for extensions. Add a test with CoolProp masked.
5. **SF-4. An extension descriptor of a core kind with no payload schema is labelled `core`.**
   `descriptor.stability` (`descriptor.py:217`, `CORE_KINDS` at `:45`) returns `core` for `record_type`,
   `correlation_form` and `data_source`, but their payload `$defs` arrive only with ADR 0061's WO. I measured: an
   extension `record_type` with payload `{"anything": true}` registers as `stability: core` with no `preview_kind`
   notice. *Remedy:* for a non-built-in, return `preview` while the kind has no `PAYLOAD_DEFS` entry. It then becomes
   `core` automatically when the schema lands. Add one test.
6. **SF-5. The `convention` space rejects conventions the registry's own payloads name.** `tokens.CONVENTIONS`
   (`tokens.py:49`) holds four names, but the legacy table records `WILSON-IG-ref-v1` as `reference_convention` for
   `wilson-ig-v1` and `wilson-ig-v2`. *Remedy:* ruling W1-8. Add the two names after the §3 note is written, and add a
   test that every legacy `reference_convention` (and every `per_component` value) is a valid `convention:` name.
   `registry_sha256` does not move, because no built-in provides a `convention:` token.
7. **SF-6. E-F1-4 does not pin which descriptor holds which module.**
   `test_e_f1_4_the_implementation_sets_are_f0s_m9_set` (`tests/test_f1_legacy_builtins.py:403`) compares only the
   union with M9. A generator that swapped `pr-c1-v1`'s and `pr-lib-v1`'s module sets would pass E-F1-1 to E-F1-4. Each
   self-hash would then track the other provider's code, and an attestation (D9) would follow the wrong file. *Remedy:*
   for each legacy method, assert that `modules` holds `inspect.getfile(type(provider))` relative to `src/` (the test
   already constructs every provider). For each unit, assert that `modules` holds the M9 module that declares its
   `MODEL_ID`/`MODEL_IDS` (F0's rule).
8. **SF-7. ADR 0019 Amendment 7 is stale after WO4b.** At `docs/adr/0019-application-contract-v1.md:242-244` it still
   lists "`unsupported` (the draft form until F1-WO4b)". The draft form now refuses `revision_unsupported` (a
   schema_version other than 1; a component set that selects no method, with `detail.unbound`) and `invalid_request`
   (a member it cannot read). *Remedy:* replace that clause.
9. **SF-8 (needs a decision). Process start cost.** A cold `default_registry()` takes 0.29 s here: jsonschema
   validation of the 42 built-ins 0.15 s, validator construction 0.05 s, normalisation and self-hash 0.07 s, the
   entry-point scan 0.02 s. Every CLI command, every `LocalApplication.open`, and the first message render of any
   process (job workers included) pay it. The built-in tables are generated, and `--check` holds them. *I would:* in
   WO5, skip runtime schema validation of a built-in table when the SHA-256 of its bytes together with the descriptor
   schema's bytes equals a digest the generator writes and `--check` holds. Keep the self-hash, which is D10's identity.
   Also cache `registry_sha256` on the closed registry. This keeps D8's "a built-in failure raises" for any edited
   table. Alternative: accept 0.3 s for 0.5, if the full gate's wall-time budget holds.
10. **N-1.** In `catalogue/registry.yaml:19`, `capability_missing`'s summary says "nothing provides". The method and
    the definition lack it; another method may well provide it. The example at `:25` cannot occur: `pr-lib-v1`
    provides `conn:nTP-v1`, so the real refusal names `legacy:coolprop-heos-v1|legacy:iapws95-v1`. *Remedy:* "…: neither
    the property method nor the stream definition provides {capability!raw}.", with the example
    `{unit: syn001.tp_flash, method: pr-c1-v1, capability: "legacy:syn001|legacy:wilson-ig-v2"}`.
11. **N-2.** The comment at `benchmarks/f1/numerical_policy_external.yaml:13`, "no preimage holds a float", is false. D2
    lets `limitations` params be numbers, and a preview payload may hold floats. The `exact` classification stays
    right, because the digests are of declared data. *Remedy:* reword the comment.
12. **N-3.** `token_problem` (`tokens.py:191`) lets *any* built-in provide `legacy:` tokens, but D4 says "built-in
    legacy descriptors only". A future built-in table could leak into the closed family. *Remedy:* pass `legacy_form`
    through and refuse `legacy:` outside the `legacy` table.
13. **N-4.** `discovery.CatalogueCheck.load` imports MSG's private `_yaml_load` (`discovery.py:210`). *Remedy:* MSG
    exports a public loader.
14. **N-5.** The draft form's `not_found` for an unregistered model id (`capabilities.py:127-139`) does not say which
    instance holds it. *Remedy:* add `pointer: /revision/instances/<i>/model/id` to the detail.
15. **N-6 (for WO5).** Compute E-F1-5's real constant from `Registry.build(builtin_tables=discovery.builtin_tables())`,
    not from `default_registry()`, which includes whatever extensions the environment has installed. Review notes N1
    (`builtin-sha256.txt` `--write/--check`), N4 (exact-case module paths: on macOS and Windows a wrong-case path
    resolves, on Linux it quarantines) and N5 (zip and frozen builds: the built-in import root has no files, and the
    process registry fails to build) are still open. Record N4 and N5 as declared limits in WO5.

## Edited checks and expectations (none relaxed)

- **T07 G20** (`cache` 39 to 40, `global` 2 to 3, `ContextVar` 1 to 2, `threading.local` 0 to 1). Each new hit has its
  own allowlist entry with a justification that holds: immutable validators, one closed process registry, a per-thread
  build depth, a per-context usage record. Sound.
- **Numerical-policy `ADDENDA`** gains `f1`, and `test_m05`'s pinned order follows. This is additive: three exact
  `sha256` names in their own table, as ST's and OPT's are. Sound (comment: N-2).
- **T08.A32 `SHIPPED_DATA`** gains `registry/builtin/*.json`: generated from the project's code. The CoolProp fluid
  names in it are identifiers, not third-party data. Sound.
- **`test_package_imports.LAYERS`** gains `registry`. Registering a new top-level package is required by
  `test_no_unexpected_layers`; the import scan is untouched. Sound.
- **MSG-G2** now also scans `Coded(...)`. This is a strengthening: registry codes without an entry now fail G2.
- **The count and strip edits** in the M02, M04, T07 and T08 tests follow the established "strip the later package
  first" pattern. With F1 stripped, the served list equals X04's `6be1c002…` exactly, and
  `test_f1_control_c_9_left_in_place` fails at c_9.

## Rulings (each with its default; work proceeds on the default)

- **W1-8: yes, §3 is missing them.** ADR 0047 C1 required `interfaces-frozen.md` §3 to gain a note naming
  `WILSON-IG-ref-v1` and `S10-VER-ref-v1` on acceptance (2026-10-30), and it was never written. The design lane writes
  that note. F1 then adds both names to `tokens.CONVENTIONS` (SF-5), and D4's source cell reads "§3 (six conventions)".
- **W1-17: do not scope A31(a) now.** One statement of the kind list, in the schema enum, is the better design anyway.
  ADR-F6's WO, which first names `semantic_role` in `src/`, amends A31(a) to scope it to readers of the revision field.
- **W2-2: accepted.** D6 itself says the table records the fluid-to-convention map, and E-F1-3 needs the per-fluid
  property lists to be faithful. Erratum in D6: "`per_component`: null, or for CoolProp a map fluid to
  `{reference_convention, properties, derivative_inputs}`; the top-level lists are those every fluid declares, in
  describe order" (MF-1).
- **W2-5 and W3-10: accept `factory_unavailable`** (refusal, `not_supported`) for a null factory and for a legacy
  method with `selectable: false`. Keep `basis_provider` as D6's factory. Naming the classes' own constructors would
  make `pr-lib-v1` and `wilson-ig-v1` constructible through the registry, against risk 1's default. Add the code to
  the ADR's code table (MF-1).
- **W3-12: a v1 revision names no registry version.** The binder leaves a native model's `model.version` unread, and
  for a variant-backed model the field is a variant pin (`revision_binding.py:1982`). Rule for D8: "a schema_version 1
  revision's unit references resolve to the legacy descriptor's version (1.0.0); `model.version` is never a registry
  version". The draft form's highest-version default (W4b-2) already gives the same result, because legacy namespaces
  are reserved. v2 revisions carry registry versions (ADR-F2).
- **W4a-2: one kind per HTTP request; no comma form.** A comma form would be a second spelling of one request,
  parsed only on HTTP. Python, CLI and MCP take the list, and the generated HTTP route page states the limit.
- **W4a-13: accept the reading.** `gap.capability` is the entry's fixed text, and the missing token is
  `params.capability`, which R-931's agentic layer reads. MSG keeps static gaps (ADR 0058). The D5 sentence and the
  code-table cell are edited in MF-1.
- **ADR 0019 Amendment 7 as "Proposed": correct.** It flips to Accepted in the commit that accepts ADR 0060, and its
  refusal list is fixed now (SF-7).
- **W4b-4: accepted.** On 12 revisions the binder refuses before its model check, so "for the same instance" can be
  observed only on the other 38. The test still pins the 12 as refused-first and unchanged, and checks
  `check_admission` on all 50 against `MODEL_BASES`. E-F1-11 is re-worded to say this (MF-1).
- **"49": a miscount.** M1 holds 50 revisions (T07's `CORPUS`); the ADR reads 50 (MF-1).
- **Unregistered model id: `not_found` for the whole report, as built.** D11 states it, and a per-instance
  `model_unsupported` would need a nullable `unit_version` in the frozen `AdmissionPair` and would lose the
  suggestions. Add the instance pointer (N-5).
- **The two tool descriptions: approved with these edits.** After the edits, re-take `F1_FILE_SHA256`, D_9 and
  `F1_SERVED_SHA256` within c_9 and R-1030, and record the design-lane review in `REVIEW.json`.
  - `list_capabilities.md` (1360 to 1467 characters):
    1. Replace "and the registry's evidence fields origin, evidence_class (core, reviewed or unreviewed) and
       stability." with "and the computed fields origin, effective_status, evidence_class (core, reviewed or
       unreviewed) and stability (core or preview). Trust evidence_class, not the declared status." An extension
       may declare `released`, and only `effective_status` and `evidence_class` say what counts.
    2. Replace "Being listed is not being selectable in a revision or verified;" with "Being listed is not being usable
       in a revision (payload.bindable, payload.selectable) or verified;".
  - `check_admission.md` (1489 to 1488 characters):
    1. Replace "names what nothing provides in params.capability" with "names in params.capability what the method and
       definition lack". Other methods may provide it, and the old wording tells an agent to stop looking.
    2. Replace "(list_capabilities shows what each provides)" with "(see list_capabilities)".
    3. Replace "(null for a pair)" with "(null in the pair form)".
- **Performance (SF-8):** the digest short-cut in WO5. Default if Frank prefers no change: accept 0.3 s for 0.5.

## What Frank decides

1. Accept ADR 0060 with the MF-1 errata (and ADR 0019 Amendment 7 with it). Default: accept once the errata are in.
2. Review the two tool descriptions in their edited form. Default: approve as edited above.
3. Startup cost (SF-8): about 0.3 s on every command and process start. Default: the digest short-cut in WO5.

**Not examined:** `scripts/registry_builtin.py` beyond its `--check` and the E-F1 tests that judge its output; the
HTTP and MCP binding code beyond E-F1-10; the two schema files line by line (their tests pass); the wheel build; ruff
and mypy; the decision-register text of R-1030.
