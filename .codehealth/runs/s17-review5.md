# S17 review 5 (reviewer, 2026-11-13): revision_binding.py steps 5a21f253..e0c43abe (7 steps)
Verdict: 7 accepted (2 accept, 5 accept-with-note), 0 rejects. No behaviour difference found (check order, first
refusal, exception types, messages, lazy imports unchanged).
- d3be100e note: `_model_refusal` calls `_basis_refusal` (:1725), which always returns an Unbound; the suffix
  `_refusal` now means `Unbound | None`. Rename in a names pass.
- db8de9f3 note: `_built_instances(provider: PropertyProvider)` (:2139) is weaker than the caller's `PropertyMeter`;
  units capture the provider at construction (:2003-2006). Annotate `PropertyMeter` (TYPE_CHECKING import).
- d9840541 note: `_port_refusal` docstring "for a single port" means a port of multiplicity 1.
- 1fe361e5 note (should fix): `_split_key_refusal` (:2192) defined after `_port_refusal` (:2171), called before
  (:2018 vs :2023): swap (rule 5).
- b92b0490: commit message says the first rule moved; only its `{key}` half did.
- e0c43abe note: readability neutral; `_unadmitted` is one family table (units design §4.7); lifting only the thermal
  family is nesting credit. Peel no further.
- Across steps (should fix): `bind_revision_flowsheet` docstring (:1977-1980) lists none of its phase helpers (rule 7).
- bind_revision_flowsheet reads as named phases :1996-2025; stopping at 9.5 is right.
- Not from these steps: `_variant_backed_models()` (~2 ms) is called once per instance in `_model_refusal` (:2101);
  hoisting it is a separate (performance) commit, outside S17's bitwise steps unless shown pure.
Playbook proposals: rule 5 ext (insert a later helper in call order); rule 7 ext (first clause/phase helper also
listed in the caller's docstring); rule 12 refined (widening is fine unless the stronger type carries an invariant
the output depends on: metering, canonical form); naming `_<clause>_refusal` = `Unbound | None`; extract-phase
when-not: a dispatch whose branches are the families of one design table, lift all or none (e0c43abe); commit
messages describe the moved unit in the docstring's terms (b92b0490).
