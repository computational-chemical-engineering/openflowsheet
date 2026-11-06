# W1 note edits — log of Revision 3 of `target-architecture.md`

Status: record, build lane, 2026-11-06. Applies every accumulated W1 edit to `docs/roadmap/target-architecture.md`
(Revision 2 at `82530b57`; Revision 3 is the commit that adds this file). Sources, oldest first; a later source wins
where two touch the same text. Section numbers are the note's (§2.x.n = item n of §2.x's *Design*).

- **R12, A1:** `foundation-rulings.md` §12 (edits to the note) and §13 (Amendment 1); dated before Revision 2.
- **A2, A3, A4:** rulings §14, §15, §16 (Amendments 2–4), last column of each table.
- **0060-n … 0064-n:** the "Edits `target-architecture.md` needs" list of ADR 0060–0064 (0063 and 0064 are one
  paragraph each; their clauses are numbered here in reading order).
- **P3-n:** `docs/roadmap/W1-P3-note-edits.md` items 1–33 (ADR 0065–0067 and the W1 P3 review).

Status values: *applied*; *already present* (in Revision 2, or applied earlier in this revision from an older source);
*applied (intent)* (the anchor text was absent, so the edit's intent was applied to the current text); *skipped*.

## Counts

| Source | Edits | Applied | Applied (intent) | Already present | Skipped |
| --- | --- | --- | --- | --- | --- |
| R12 (rulings §12) | 12 | 0 | 0 | 12 | 0 |
| A1 (Amendment 1) | 9 | 0 | 0 | 8 | 1 (no edit) |
| A2 (Amendment 2) | 37 | 37 | 0 | 0 | 0 |
| A3 (Amendment 3) | 5 | 5 | 0 | 0 | 0 |
| A4 (Amendment 4) | 16 | 14 | 2 | 0 | 0 |
| ADR 0060 | 9 | 9 | 0 | 0 | 0 |
| ADR 0061 | 6 | 6 | 0 | 0 | 0 |
| ADR 0062 | 7 | 6 | 0 | 1 | 0 |
| ADR 0063 | 10 | 7 | 0 | 3 | 0 |
| ADR 0064 | 10 | 9 | 0 | 1 | 0 |
| P3 (items 1–33) | 33 | 32 | 1 | 0 | 0 |

## Conflicts resolved (later source wins)

- §6 Q1 count: A2 "(R1–R9)" → A4 "(R1–R10)". §6 Q2: A3 "(R1–R9)" → A4 "(R1–R10)".
- F4 exit Q2 list: A2 "Q2.A1–A9" → A3 / 0063 "Q2.A1–A9, A11" → A4 adds Q2.A12 (a), (d), (e).
- §2.5.2 (c): A2 "(Q1.R9)" → P3-15 "(Q1.R9; registered `holdup_kind`, built-in only)".
- §2.4 routing: P3-3 and A4 (Q4.R9) refined by P3-32; written once as the new §2.4.13.
- §2.1.8 fingerprint: P3-5 (sources) and P3-33 (`configuration` role, `FSR2-` label) written together; P3-33 names
  "§2.4 identity", so §2.4.1 points to §2.1.8.
- FB-04 turbine: P3-13 adds it to the F6 exit "moved from ADR 0064 E-F5-6"; the F5 exit bullet that carried it is
  removed.

## Log

| Id | Edit (short) | Note section | Status |
| --- | --- | --- | --- |
| R12-1 | definition document: `h_mass`, `conserved_basis`, dormancy and labels | §2.1.1–2 | already present |
| R12-2 | exclusive solid role; dormancy per substream | §2.1.2–3 | already present |
| R12-3 | exact `+0.0` attributes; partition rule | §2.1.2, §2.1.4 | already present |
| R12-4 | λ1 not carried; segment partition; M per segment type | §2.1.4–5 | already present |
| R12-5 | phase id triple, injective rendering | §2.1.6 | already present |
| R12-6 | prefix rule, count lattice; claims, witness, trial set; conserved-basis slot | §2.2.2–3, §2.2.6–9 | already present |
| R12-7 | provenance axes, record types, volatile set, rights; `ELEMENTAL-ref-v1`; ADR 0001 D5.2 | §2.3.1, §2.3.6, §2.3 ADRs | already present |
| R12-8 | F2 exit Q1.A5, `probe.partition`; F4 exit Q2.A2; F5 exit τ_tm band | §3 F2, F4, F5 | already present |
| R12-9 | §6 Q1 wording; Q3–Q6, Q9 defaults replaced | §6 | already present |
| R12-10 | §7 R4 decided | §7 | already present |
| R12-11 | §8 `ComponentRecord` and `SolutionCertificate` rows | §8 | already present |
| R12-12 | pointer: Amendments 1–4 add edits | — | already present (satisfied by A1–A4 rows) |
| A1-S3 | openings re-seed; causal outlet evaluation; F6 exit Q1.A9 | §2.2.5, §2.4.1, F6 | already present |
| A1-S4 | Q5.R7; W_p and ι_p in `StabilityReport`; ι_p domain; F5 exit Q5.A9 (c) | §2.2.1, §2.2.6, §2.2.8, F5 | already present |
| A1-S9 | conserved-basis object carries M_g | §2.1.5, §2.2.9 | already present |
| A1-S10 | none | — | skipped: the row lists no note edit |
| A1-N5 | confined adsorbed phases; O3 and A3 | §2.1.3, §2.2.7, §7 | already present |
| A1-N6 | anchor bridge, `anchor_bridged` | §2.3.6 | already present |
| A1-N7 | exact order, flags afterwards | §2.2.2 | already present |
| A1-N8 | `near_critical` and `near_spinodal` | §2.2.7, §8 | already present |
| A1-N10 | Q1.R7's holdup list; F7 exit Q1.A10 | §2.5.2, F7 | already present |
| A2-A1a.1 | delete the F2 open item | §3 F2 | applied |
| A2-A1a.2 | F2 exit "Also Q3.A1–A3, A6" | §3 F2 | applied |
| A2-A1a.3 | boundary (ii)–(iii): C A = A′Π, b′ = C b; dropped species reported | §2.3.8 | applied |
| A2-A1a.4 | F4 exit refusals: Q3.A5 | §3 F4 | applied |
| A2-A1a.5 | drop the A1-a row | §6 | applied |
| A2-A1a.6 | R13 ruled | §7 | applied |
| A2-A1b.1 | anchor from the record alone; adding a method never re-anchors | §2.3.6 | applied |
| A2-A1b.2 | bridge also by the difference of formation entries (Q2.R8) | §2.3.6 | applied |
| A2-A1b.3 | delete the F4 open item | §3 F4 | applied |
| A2-A1b.4 | F4 exit "Q2.A1–A9" | §3 F4 | applied (then extended by A3, A4) |
| A2-A1b.5 | `ComponentRecord`: the anchor is an identity field | §8 | applied |
| A2-A1b.6 | drop the A1-b row | §6 | applied |
| A2-A1b.7 | R14 ruled | §7 | applied |
| A2-S5.1 | families `VAPOR`, `LIQUID`, `FLUID`, `SOLID`; qualifiers on every family; W1 core item | §2.1.6 | applied |
| A2-S5.2 | Q4.R6 (FLUID, `character`, root kept, `root_switch`), Q4.R3's v̂ key, Q4.R8 | §2.2.2 | applied |
| A2-S5.3 | "so ADR-F5 can add one…" → "(FLUID, Q4.R6)" | §2.2.2 | applied |
| A2-S5.4 | Q5.R3, R8 as extended (FLUID roots; one W per minimum) | §2.2.7–8 | applied |
| A2-S5.5 | delete the F5 open item | §3 F5 | applied |
| A2-S5.6 | F5 exit Q4.A1–A11, Q5.A1–A10 | §3 F5 | applied |
| A2-S5.7 | F2 exit, ids: qualifiers on every family | §3 F2 | applied |
| A2-S5.8 | drop the S5 row | §6 | applied |
| A2-S5.9 | Q4 "(R1–R8)" | §6 | applied (extended by A4-6) |
| A2-S5.10 | R12 ruled, O-3 closed | §7 | applied |
| A2-S5.11 | free water is `FLUID(water)` (Q4.R8) | §9.4 | applied |
| A2-S5.12 | drop "(ruling pending)" | §9.11 | applied |
| A2-HD.1 | dormancy, drain event, re-seeding per Q1.R8 | §2.5.2 (a) | applied |
| A2-HD.2 | delete the first F7 open item | §3 F7 | applied |
| A2-HD.3 | F7 exit Q1.A11 | §3 F7 | applied |
| A2-HD.4 | drop the holdup-dormancy row | §6 | applied |
| A2-HD.5 | Q1 "(R1–R9)" | §6 | applied (superseded by A4-14) |
| A2-HD.6 | R15 ruled | §7 | applied |
| A2-HD.7 | cite Q1.R8 | §9.6 (4), §9.9 | applied |
| A2-HD.8 | drop "(rulings pending)" | §9.11 | applied |
| A2-NM.1 | "pending a ruling (§6)" → "(Q1.R9)" | §2.5.2 (c) | applied (superseded by P3-15) |
| A2-NM.2 | delete the second F7 open item; drop the §6 row | §3 F7, §6 | applied |
| A2-NM.3 | F7 exit Q1.A12 | §3 F7 | applied |
| A2-NM.4 | cite Q1.R9 | §9.10 (1) | applied |
| A3-1 | neutral `mol` record without data takes `ig`, `anchor_defaulted`; `ig` = ideal-gas state | §2.3.6 | applied |
| A3-2 | F3 exit Q2.A10 | §3 F3 | applied |
| A3-3 | F4 exit "Q2.A1–A9, A11" | §3 F4 | applied (extended by A4-2) |
| A3-4 | §6 Q2 "(R1–R9)" | §6 | applied (superseded by A4-4) |
| A3-5 | ADR 0061 risk 2 enters as ruled by Q2.R9 | §7 R21 | applied |
| A4-1 | entropy datum (s° absent: s = 0, `entropy_datum`; Q2.R10) | §2.3.6 | applied |
| A4-2 | F4 exit Q2.A12 (a), (d), (e) | §3 F4 | applied |
| A4-3 | F6 exit Q2.A12 (b), (c) | §3 F6 | applied |
| A4-4 | §6 Q2 "(R1–R10)" | §6 | applied |
| A4-5 | routing: Q4.R9 | §2.4.13 | applied |
| A4-6 | O-11: "reported only" → "decides a lone fluid phase's outlet (Q4.R9)" | §6 Q4 row | applied (intent): the note has no O-11 row; the §11 O-11 part edits the rulings, not the note |
| A4-7 | F6 exit Q4.A12 | §3 F6 | applied |
| A4-8 | `std.pid` steady closure per Q5.R9 | §2.4.11 | applied |
| A4-9 | heat ports: Q5.R10 | §2.4.1 | applied |
| A4-10 | τ_idx and its example (Q5.R11) | §2.5.3 | applied |
| A4-11 | F7 exit Q5.A13 | §3 F7 | applied (wording of P3-31) |
| A4-12 | events per Q1.R10 | §2.5.2 | applied |
| A4-13 | F7 exit Q1.A13 | §3 F7 | applied |
| A4-14 | §6 Q1 "(R1–R10)" | §6 | applied |
| A4-15 | `forced_replay` per Q9.R8 | §2.7.6 | applied |
| A4-16 | TX exit: Q9.A9 | §2.7.6 | applied (intent): the note has no TX exit list |
| 0060-1 | F1 kinds: `correlation_form` (owner ADR 0061) | §3 F1 | applied |
| 0060-2 | iteration by (kind, id, version); `registry_sha256` | §3 F1 | applied |
| 0060-3 | F1 exit "(31 × 7 pairs, 54 admitted)" | §3 F1 | applied |
| 0060-4 | X01 rest: selectable through v2; v1 basis for `pr-lib-v1` needs a decision | §3 F1 | applied |
| 0060-5 | `MODEL_BASES` as reserved `legacy:` tokens | §2.4.2 | applied |
| 0060-6 | `implementation_sha256` = sha256 of [descriptor, self] | §2.3.3 | applied |
| 0060-7 | snapshot is ADR 0060 D10's; evidence classes never move an identity | §2.7.3, §2.7.7 | applied |
| 0060-8 | `Inspection` row | §8 | applied |
| 0060-9 | soft edge MSG → F1 (WO3, WO4a) | §4 table, graph, acyclicity text | applied |
| 0061-1 | F3 operations `search_records` … `assess_rights` | §3 F3 | applied |
| 0061-2 | stored object = identity projection; parameter-set matching | §2.3.1 | applied |
| 0061-3 | lock format id and orders; derived, never stored | §2.3.2 | applied |
| 0061-4 | F3 exit: S10 verification records; 149 records from 7 files | §3 F3 | applied |
| 0061-5 | R18 resolved by D12; risks 1, 2, 6 added | §7 R18, R20–R22 | applied |
| 0061-6 | `ComponentRecord` row; data-lock and `Records` rows; D1.3 kinds | §8 | applied |
| 0062-1 | templates and instances; grids inside substreams; `conserved_basis` grammar | §2.1.1, §2.1.14 | applied |
| 0062-2 | qualifier grammar and `+` set rendering | §2.1.6 | applied |
| 0062-3 | closed field table | §2.1.7 | applied |
| 0062-4 | "for v2-compiled runs"; lowered runs keep v1 fingerprints | §2.1.8 | applied |
| 0062-5 | `components[].record`; signal `quantity_kind`; lowering in 0.5 | §2.1.14 | applied |
| 0062-6 | provider-type rows unchanged; `MethodDescription`, `EquilibriumResult`; kinds | §8 | applied |
| 0062-7 | F2 exit Q3.A6 and the lowering identity (E-F2-3) | §3 F2 | already present (Q3.A6, from A2-A1a.2); E-F2-3 applied |
| 0063-1 | narrowed `data_sha256` (D2) | §2.3.2 | applied |
| 0063-2 | `describe_method()` | §2.3.3, §2.3.6 | applied |
| 0063-3 | Amendment 2–3 anchor text | §2.3.6 | already present (A2-A1b.1, A3-1) |
| 0063-4 | D4's PR-C1 rule (`pr_c1.h_ig`; `cubic.pr-v1` c_p integral) | §2.3.6 | applied |
| 0063-5 | constants in `SolvePolicy.scales` and `energy_check` | §2.3.7 | applied |
| 0063-6 | Amendment 2's (ii)–(iii) | §2.3.8 | already present (A2-A1a.3) |
| 0063-7 | `PropertyCapabilities` row → `MethodDescription` | §8 | applied |
| 0063-8 | F4 exit "Q2.A1–A9, A11" | §3 F4 | applied |
| 0063-9 | F4 exit Q3.A5 | §3 F4 | already present (A2-A1a.4) |
| 0063-10 | F4 exit E-F4-3 | §3 F4 | applied |
| 0064-1 | FLUID text | §2.2.1–2 | applied |
| 0064-2 | `root_switch` | §2.2.2 | applied |
| 0064-3 | dispatch (v1 path → T05b; v2-compiled → generalised controller) | §2.2.3 | applied |
| 0064-4 | `EquilibriumResult` | §2.2.6 | applied |
| 0064-5 | TP-only providers | §2.2.6 | applied |
| 0064-6 | `FlashResult` row → `EquilibriumResult` | §8 | applied |
| 0064-7 | certificate row → optional `phase_report` | §8 | applied |
| 0064-8 | §9.4 (1): `FLUID(water)` and D6 | §9.4 | applied |
| 0064-9 | F5 exit Q4.A1–A11, Q5.A1–A10 | §3 F5 | already present (A2-S5.6) |
| 0064-10 | F5 exit E-F5-2 | §3 F5 | applied |
| P3-1 | `contribute(declaration, …)`, `reseed`; declaration SHA; manifest list; no-read accessors | §2.4.1 | applied |
| P3-2 | forms selected at dormancy, `zero_flow_form`; coverage generated | §2.4.1 | applied |
| P3-3 | routing rule of A2-b | §2.4.13 (pointer in §2.2.2) | applied |
| P3-4 | unit-owned and parameter-id fields | §2.1.7 | applied |
| P3-5 | `compiled-problem-structure-v2` with `sources` | §2.1.8 | applied |
| P3-6 | matrix axes incl. the definition template; `coverage-bases.yaml`; legacy outside | §2.4.3 | applied |
| P3-7 | v1 adapter limit; `scripts/f6_parity.py`; expected parity | §2.4.4 | applied |
| P3-8 | flattening depth ≤ 8, `template_cycle`, `template_unavailable`; ids order-free | §2.4.6 | applied |
| P3-9 | node set; n-ary `add`/`mul` as written; dimension inference | §2.4.7 | applied |
| P3-10 | `cosimulation`, `cape_open` refused typed | §2.4.8 | applied |
| P3-11 | `std.pid` only; others TX's seed; `controller_regime` | §2.4.11 | applied |
| P3-12 | `equipment_class` seeds one class per `std.*` unit, `preview` | §2.4.10 | applied |
| P3-13 | F6 exit: FB-04 turbine on `std.turbine`; routing; zero-flow coverage; `std.pid` in the seed | §3 F6 (and F5) | applied |
| P3-14 | `ModelManifest` and `UnitModel` rows | §8 | applied |
| P3-15 | holdup columns; "(Q1.R9; registered `holdup_kind`, built-in only)" | §2.5.2 (a), (c) | applied |
| P3-16 | dynamic scenario document (ADR 0008 C7 relocated) | §2.5.2 | applied |
| P3-17 | `differential_map` in structure document v2 for dynamic problems | §2.5 migration proof | applied |
| P3-18 | run-kind payload, seed table, `job_operation`, seeded `validation_task` | §2.5.9 | applied |
| P3-19 | progress members; partial artifacts as output events | §2.6 C6 | applied |
| P3-20 | Q1.A11, A12 on a reference integrator; TX re-runs on its BDF | §3 F7 | applied |
| P3-21 | accumulation, `CompiledProblemMetadata`, Job, checkpoint rows | §8 | applied |
| P3-22 | "Time inputs come from the dynamic scenario document." | §9.6 | applied |
| P3-23 | v2-compiled bundles carry the lock; v1-path unchanged; `artifacts/` layout | §2.7.1 | applied |
| P3-24 | replay compares used extensions only | §2.7.3 | applied |
| P3-25 | decision-record entry kinds and classes; `forced_replay` replaces `compatible_reproduction` | §2.7.6 | applied |
| P3-26 | evidence report artifact; no evidence notices on the certificate | §2.7.7 | applied |
| P3-27 | F8 exit: usage cross-check; v1-path runs byte-identical | §3 F8 | applied |
| P3-28 | `RunManifest` row members and build lines | §8 | applied |
| P3-29 | "the run report and the certificate carry the notices" → "the run's evidence report carries the notices" | §2.7.7 | applied (intent): §2.3 never restated D9's propagation; the sentence is in §2.7.7 |
| P3-30 | F8 note column | §4 | applied |
| P3-31 | F7 exit index bullet → Q5.A13 (a)–(f) | §3 F7 | applied |
| P3-32 | `phase_routing` `vapor` port; lone `vapour_like` FLUID; ≥ 2 FLUID by SQ-F6-5 | §2.4.13 | applied |
| P3-33 | `configuration` source; label `FSR2-<configuration_sha256[:12]>` | §2.1.8 (pointer from §2.4.1) | applied |

## Not changed (no edit requested)

- §6 Q5 and Q9 rows keep "(R1–R8)" and "(R1–R7)", although Amendment 4 adds Q5.R9–R11 and Q9.R8 (none of its rows names
  a §6 edit for them).
- §2.2's *Foundation* paragraph still says ADR-F5 "reshapes `SolutionCertificate.phase_branch` and `phase_stability`";
  ADR 0064's edits change only the §8 row (optional `phase_report`).
- §1, §5 (W1 steps) and the *Inputs* paragraph ("with Amendment 1") are unchanged; the Revision 3 line records the rest.
