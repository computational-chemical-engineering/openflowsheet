# ADR 0057 — Roadmap and target architecture: foundations F0–F8 before the features that need them

**Status:** **Accepted, 2026-11-02** (Frank, roadmap stage 5: "Accept as is" — dynamics in 0.7, the design toolkit in
0.8). Proposed the same day. Its normative text is
`docs/roadmap/target-architecture.md` (Revision 2, "the note") for structure and `docs/roadmap/roadmap.md` for order.
`docs/roadmap/foundation-rulings.md` (with Amendment 1) is input to ADR-F2 to ADR-F5 and becomes archival once they adopt
it. Nothing is built by this ADR.
**Author:** design lane (`architect`), roadmap stage 4c, from `docs/roadmap/brief-architect-2-final.md`. Scientific
semantics are the specifier's rulings; the independent review is `docs/roadmap/review-roadmap.md` (verdict: finalise
after the listed fixes, which the note applies).
**Builds on:** R-923 (co-simulation allowed), R-924 (no unnecessary restrictions), R-925 (restrictions lifted as
planned packages), R-926 (user-fetched and user-licensed data), R-927 (full real-simulator scope, design quality
first); ADR 0056 with Amendments 1–2; blueprint D01–D20, with no departure; plan v1.2 §1.3, §2.1 and §2.2;
`docs/roadmap/decisions.md`.
**Subordinates:** the release-line tables of ADR 0056 (its base order and Amendment 1). They become defaults under
`roadmap.md`. ADR 0056's package list, per-package entry conditions and superseded-policy list stand unchanged.

## Context

Up to 0.3, five core structures were fixed for the cases each release needed: the stream state `nTP-v1`, two-slot phase
handling, one provider per revision selected by a file path, unit families that encode their provider's physics, and
steady-only problems. The revision schema has energy and signal port kinds but forces `nTP-v1` on every connection. Every
package that R-927 put in scope breaks at least one of these structures. Each break found late would cost a migration
across evidence, replay identity and frozen interfaces.

## Decision

**D1 — Foundations first.** Nine foundation packages are built before the features that need them, in this order: F0
corpus identity gate; F1 extension registry and computed admission; F3 component data core; F2 material model and
`ProcessRevision` v2; F8 identity, replay and evidence v2; F4 property methods and thermo face; F5 phase-equilibrium
framework; F6 unit-model framework v2; F7 problem IR v2 and run kinds. A package that could fix a core structure is
built only after the foundation that owns the structure has been designed and its ADR Accepted. Packages that fix no core
structure may go earlier: the 0.4 set (MSG, ST, X04, X05, X02, OPT, X10 inventory, RRC). All design for F1–F8 runs
in design wave W1, during 0.4. After it, each package's design pass runs one release line ahead of its build.

**D2 — The v2 grammar and its freeze points.**
- Two-level material model: providers see an evaluation state; flowsheets see registered, versioned connection
  definitions. The general material definition is `(n, ĥ, P)` with mass-specific `ĥ` on one convention per flowsheet
  (`ELEMENTAL-ref-v1` by default); T is derived. `nTP-v1` stays one registered definition, byte for byte.
- Three connection kinds, each with a registered definition: material, energy (`heat-v1`, `work-v1`; positive from
  `from` to `to`) and signal (`signal-v1` typed by quantity kind). Endpoints are ports, probes on any quantity, or
  declared manipulable parameters. Controllers and utilities are units. Reaction sets are a core section. A reserved
  `sections` mechanism, owned through F1, guards against a v3; none of the ten package sketches needed it.
- One thermal coordinate per flowsheet; legacy units only on `nTP-v1` flowsheets; no converters at definition
  boundaries. Specifications and decisions may target derived quantities (T, β, pH, d50, RVP and others).
- The v2 variable-id grammar is injective by construction: a separator outside the id alphabet at every user-id
  boundary, and every v2 id disjoint from every legacy id.
- `ProcessRevision` v2 is a new schema version; no v1 document is migrated (ADR 0002 D7). Its *core* is frozen at the
  end of W1, and changes after that only by ADR. The *preview* slots (property-method sets, phase assertions,
  templates, the `expression` kinetics kind) are frozen at the end of 0.6. Until then, documents that use them are
  marked preview.

**D3 — Legacy freeze, equivalence and retirement.**
- *Byte-level freeze.* Identity-bearing legacy modules (whose bytes enter an `implementation_sha256`, or are imported
  into such a hash set) are never edited. Registration, adapters and type widening live in new modules. F0 checks a
  per-file SHA of each frozen module. A `.gitattributes` with `eol=lf` for hashed files lands with F0, and new modules
  self-hash LF-normalised bytes. A legacy bug fix is a registered change to numerics with new references, decided as
  such.
- *Equivalence.* F4: composed methods that delegate to the legacy kernels reproduce the legacy provider bitwise on the
  native, pre-shift layer; the convention shift is checked separately (within 4 ulp). Re-implemented methods agree in
  the R2 comparison of the K04 policy, with a registered difference record. F6: `std.*` agrees with the legacy units on
  a physical projection (amounts, P, T, Ḣ without the convention shift, phase amounts and β, duties and work) in two
  steps: first on `nTP-v1`, then from `nTP-v1` to `ĥ`.
- *Retirement.* A legacy family whose every unit has a `std.*` counterpart passing step 1 on all its corpus cases is
  closed to new v2 work. Edits refuse to add its units to a v2 revision; existing documents keep validating and
  running; v1 revisions run it unchanged forever.

**D4 — The owned integrator and LOA.**
- The DAE step loop is owned (D01). It follows the published DASSL/IDA BDF: the fixed-leading-coefficient form, orders
  1–5, the local error and convergence-rate tests, and a modified-Newton corrector with Jacobian reuse and SuperLU
  (D03). IDAS through CasADi is a cross-check: TX's acceptance registers a gate on trajectories and event times.
- `DynamicSpec` admits conserved holdups (Q1.R7), rate states (a new accumulation kind `state_rate`, for controllers)
  and discrete states assigned only at events. The variable set is constant over a run; `M` stays a constant 0/1
  selection.
- MINLP synthesis uses owned logic-based outer approximation. Every NLP is a fixed-structure revision, solved and
  certified. The master MILP is in reduced space, with cuts from the parametric twin. It starts from a set covering of
  the disjuncts, and HiGHS is the default solver. One registered superstructure small enough to enumerate must give the
  same answer as full enumeration; the evidence otherwise reads "local per NLP; no global claim".
- D02 and D03 hold; scale is a measured risk (the F6 scaling gate).

**D5 — One contract.** Rules C1–C8 of the note §2.6 bind every package: one OPERATIONS row set per capability on all
transports; discovery and admission checks (by triple or by draft revision); catalogued messages with a `notice` kind;
unit conversion only at the boundary; projections outside certificate identity; progress and checkpoints; branches in
the store; no code to author.

**D6 — Release lines.** `roadmap.md` gives the order: 0.4 boundary work, F0 and W1; 0.5 X07a, F1, F3, F2, F8, X06;
0.6 F4, F5, F6 and the multiphase packages, closing with Seider VCM; 0.7 F7, TX, X13, X07b; 0.8 the design toolkit; 0.9
batch, relief, synthesis and electrolytes; 1.0 solids, polymers and P&ID. MSG before X04 stands (Frank). ADR 0056's
release lines are subordinate to this order. FB-04 (1) is dropped as a 0.4 legacy fix; F5 and `std.turbine` solve it.

**D7 — Open items, each with a proposed default.** The specifier rules on the first four at the start of W1, and each
gates the foundation ADR named; the fifth does not gate, since ADR-F6 takes its default and X14's specification
confirms it:
- A1-a, the conserved-basis condition at method boundaries (ADR-F2): the invariant condition b′ = C b.
- A1-b, the anchor's dependence on the method set (ADR-F4): the anchor is a function of the record only.
- S5, phase families under one fluid model (ADR-F5): a `FLUID` family, and qualifiers for confined fluid phases.
- Holdup dormancy and non-material holdups (ADR-F7): the stream rules applied to holdups; unit-owned conserved
  holdups admitted.
- The verdict of the `heat_direction` check (ADR-F6, specified by X14): a judged check, as the exchanger's are today.

## Existing ADRs this amends, and the ADR that carries each amendment

This ADR amends none directly. Each change is made, for v2 documents only, by the foundation ADR named.

| ADR | Amendment | Carried by |
| --- | --- | --- |
| 0001 | D1.3: kinds `specific_enthalpy`, `specific_entropy`, `segment_molar_flow`, `segment_molar_mass` (and `power` if absent). D2, D3: the general definition, dormancy and labels | ADR-F2 |
| 0001 | D5.2: explicit recorded shifts to the flowsheet convention; `ELEMENTAL-ref-v1` joins D5's list | ADR-F4 |
| 0002 | D7: `ProcessRevision` v2, `Specification` v2; D4: record SHAs inside `content_hash` | ADR-F2, ADR-F3 |
| 0003 | `CompiledProblemMetadata.differential_map` (nullable) | ADR-F7 |
| 0005 | Count lattice over interchangeable slots, the `relabel` record, the discrete-coordinate product signature | ADR-F5 |
| 0007 | Decision records and `forced_replay`; R-classes for adaptive solvers | ADR-F8 |
| 0008 | C7 and C8 made concrete; C10 reversed for `state_rate`; D1 unchanged | ADR-F7 |
| 0011 | D2: a new decision naming `ELEMENTAL-ref-v1` as the datum; per-component reaction consistency | ADR-F4 |
| 0012 | v2 phase handling; D7/D8 not applicable to `ĥ` definitions | ADR-F5, ADR-F2 |
| 0013 | Not applicable to `ĥ` definitions; unchanged for v1 | ADR-F2 |
| 0019, 0020 | `submit_run(kind, documents)`, `ValidationReport` tasks, progress events; per-package OPERATIONS rows | ADR-F7; each package's ADR |
| 0025 | Per-platform reference records for foundations | ADR-F8 |
| 0032 | Decisions on derived quantities; the NLP route inside LOA | OPT's ADR; X24's ADR |
| 0033, 0034 | External units over `UnitModel` v2 (ADR-F6); co-simulation as R3, generalising 0034 D6 (ADR-F8) | ADR-F6, ADR-F8 |
| 0050 | D1 for v2 records (ADR-F3); D3 for new families (ADR-F6); D5 (ADR-F4) | ADR-F3, ADR-F4, ADR-F6 |
| 0051 | D1 for v2 documents (phase assertions replace declared regimes) | ADR-F5 |
| 0052 | Functional programs with parameters from non-revision documents; D5 untouched | ADR-F7 |
| 0056 | Release lines subordinate to `roadmap.md` | this ADR |
| `interfaces-frozen.md` §1, §3 | Widened provider types; `ELEMENTAL-ref-v1` | ADR-F2, ADR-F4 |

## Reason

- R-927 asks for a real simulator, well designed, flexible and agent-usable, and is not in a hurry. The cheapest time
  to find structural breaks is before anything of the new scope is built. The note maps every package onto foundations
  and sketches the ten hardest against the grammar before the freeze (note §9). Every break found had an additive fix
  inside a foundation not yet built; no sketch needed a v3.
- One new revision version, with a core frozen early and slots frozen after their line acceptance, costs one permanent
  reader. Freezing everything early would risk a v3; never freezing would break the frozen-schema promise.
- The byte-level freeze is the only route to a bitwise proof: any byte edit moves a self-hash and with it cache keys and
  replay identity. Without a defined equivalence and a retirement rule, two unit code paths would be an open-ended cost.
- Owning the step loop serves `forced_replay` (D20), attempt-sized event segments (ADR 0005) and co-simulation
  communication points. Following DASSL/IDA closely and cross-checking against IDAS avoids inventing an integrator.
- Big-M and hull relaxations would put dormant streams of undefined composition into every relaxation, and their
  subproblems could not be certified; LOA keeps every NLP a certified fixed-structure solve.

## Affected requirements

- **R-923:** TX includes co-simulation as an R3 run kind.
- **R-924:** every unbuilt capability returns a typed refusal or carries a declared limitation (T-coordinate
  definitions stay admitted; `dae_index_near_singular`; `delay_unsupported`).
- **R-925, ADR 0056:** each lifted restriction maps to a package with its foundations (note §4).
- **R-926, R-706:** records live in the user's project store and travel by reference unless their rights permit.
- **R-927:** every package in scope is placed.
- **Blueprint D01–D20:** unchanged. D09 is realised by F5; D18's adapters (CAPE-OPEN, DEXPI, co-simulation) arrive as
  F1 extensions.
- **Plan v1.2:** §2.1 and §2.2 change only through the foundation ADRs listed in the note §8.

## Migration impact

None at acceptance; this ADR changes no code, schema or evidence. Each foundation proves its own migration with F0 at the
old configuration, plus its named proof: decision equivalence for F5; re-composition identity for F4; `std.*`
equivalence for F6; replay of the 0.3.0 bundles for F8. v1 documents, legacy providers, legacy unit families and every
registered fixture keep their numbers. Released behaviour stays exactly as it is until the package that lifts each
restriction lands.

## Acceptance evidence

- **For this ADR:** Frank's stage-5 decision on the note and the roadmap; the review's listed fixes applied (the note's
  Revision 2 changelog). The reviewer pass on this ADR set was the stage-4 review.
- **For the plan it sets:**
  - F0 green on `main` before any foundation merges;
  - ADR-F1 to ADR-F8 Accepted at the end of W1, each after the specifier ruling on its open items (D7);
  - each foundation's exit tests (note §3) with its evidence manifest at `tested` and its reviewer pass;
  - each line's acceptance case (`roadmap.md`).
- **What this ADR does not establish:** that any foundation works. Nothing has been built or run. The numbers in the
  note are design gates and defaults (scaling slope 1.3, batching 0.1×, `c_ref`), to be measured and amended by their
  foundation ADRs if the measurements say so.
