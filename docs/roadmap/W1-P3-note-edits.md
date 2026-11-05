# Edits `target-architecture.md` needs after W1 P3 (ADRs 0065–0067)

Status: list, 2026-11-05, for the orchestrator to apply once the P3 review has ruled. Line numbers refer to the note at
`be742832`. Each edit names the ADR decision that carries it.

## From ADR 0065 (F6)

1. §2.4 Design 1 (~451): signature `contribute(declaration, wiring, material, mode)`; add the optional `reseed`; the
   declaration is a canonical document whose SHA enters the fingerprint (D1, D3). Add to the manifest list: internal
   variables, phase routing, per-port reactivation kinds, the coverage recipe, the execution class, semantic roles (D2).
   Q5.R7's no-read rule is enforced by the `amount_weighted`/`raw` accessors and the opening check (D6).
2. §2.4 Design 1, zero-flow bullet: forms are selected exactly at dormancy and carried as the discrete coordinate
   `zero_flow_form` (ADR 0012 D12 generalised); coverage is generated (`zero_flow_form_missing`) (D7).
3. §2.2 (phase labels) and §2.4: add the routing rule of A2-b: split points by family then density among LIQUID slots;
   `single` points by mass density; one FLUID phase by `character` (SQ-F6-1); fixed at openings, recorded as
   `phase_routing`, `routing_order_changed` at closure (D9).
4. §2.1.7: unit-owned fields `Q[port]`, `W[port]`, `x`, `xi`, `N`, `A`, `U`, `K[kind]`, `r`; parameter-id fields `p`, `z`
   (D4).
5. §2.1.8: the v2-compiled fingerprint is `compiled-problem-structure-v2` with `sources` (compiler, data lock,
   definitions, expressions, templates, unit declarations); the revision's `content_hash` is not a source (D3).
6. §2.4 Design 3: the matrix axes include the definition template; generated cases read
   `benchmarks/f6/coverage-bases.yaml`; legacy units are outside the generated cases (D16).
7. §2.4 Design 4: the v1 adapter admits only legacy units without a phase-selecting point
   (`legacy_unit_not_adaptable`); parity is computed by `scripts/f6_parity.py`; `thermal` is expected to reach parity
   in 0.6, `syn001` and `c1` not (D17).
8. §2.4 Design 6: flattening depth ≤ 8, `template_cycle`, `template_unavailable`; ids independent of array order (D13).
9. §2.4 Design 7: the node set, n-ary `add`/`mul` evaluated as written, no canonical reordering, dimension inference
   (D12).
10. §2.4 Design 8: `cosimulation` and `cape_open` refused typed until TX and X15 (D14).
11. §2.4 Design 11: F6 seeds `std.pid` only; ratio, lead–lag, selector and split range are TX's seed; saturation closure
    conditions and `controller_regime` adjacency (D10).
12. §2.4 Design 10 and 12: `equipment_class` seeds one class per `std.*` unit, `preview` (D15).
13. §3 F6 exit: add "the FB-04 turbine `VERIFIED` on `std.turbine` (moved from ADR 0064 E-F5-6)", "A2-b routing
    recorded and restarted by adjacency", "zero-flow coverage generated"; the seed list gains `std.pid`.
14. §8 `ModelManifest` row: add internal variables, routing, reactivation, coverage, execution class; `UnitModel` row:
    "v1 units without phase-selecting points run through an adapter".

## From ADR 0066 (F7)

15. §2.5 Design 2 (a): "the holdup columns mirror the carried indices of the held definition, plus one energy holdup
    per control volume"; (c): "pending a ruling (§6)" → "(Q1.R9; registered `holdup_kind`, built-in only)" (D2, D3).
16. §2.5 Design 2: time inputs, scenario events and the horizon live in a dynamic scenario document beside the
    revision, not on `Specification` (ADR 0008 C7 relocated) (D5).
17. §2.5 migration proof: "`differential_map` is absent for every steady problem; for dynamic problems it is a member of
    the structure document v2" (D4).
18. §2.5 Design 9: run-kind payload, the seed table with statuses, `job_operation` (`simulation` aliases `solve`),
    extension kinds map to a seeded `validation_task` (D10, D11).
19. §2.6 C6: progress members `time_s`, `time_end_s`, `segment`; partial artifacts are output events (D12).
20. §3 F7 exit: Q1.A11 and A12 run on a test-only reference integrator; TX re-runs them on its BDF (D16).
21. §8: accumulation-kinds row adds the F1 kind `holdup_kind`; `CompiledProblemMetadata` row: "last field, default
    `None`, serialised only when set"; Job row: operation `run`, artifact kinds of ADR 0066 D12 and ADR 0067 D3;
    checkpoint row: envelope ADR-F7, transient body TX.
22. §9.6 TX: "Time inputs come from the dynamic scenario document."

## From ADR 0067 (F8)

23. §2.7 Design 1: "A bundle of a v2-compiled run carries the data lock…"; v1-path runs (lowered included) are
    unchanged; layout under `artifacts/` including `records/` (D1, D3, D4).
24. §2.7 Design 3: replay compares the *used* extensions only; unused differences are counted, not decisive (D5).
25. §2.7 Design 6: decision-record entry kinds and classes; `forced_replay` replaces `compatible_reproduction` for runs
    with decision records (D8).
26. §2.7 Design 7: the evidence report artifact; the certificate carries no evidence notices (D6).
27. §3 F8 exit: add "the usage cross-check holds for every v2 run" and "v1-path runs byte-identical".
28. §8 `RunManifest` row: members `bundle_format`, `data_lock_sha256`, `extensions_used`, `run_kind`, `documents`,
    `environment.registry`; built 0.5 (WO1–WO3), 0.6 (WO4–WO6), 0.7 (WO7).
29. §2.3 (F1, wherever ADR 0060 D9's propagation is restated): "the run report and the certificate carry the notices"
    → "the run's evidence report carries the notices".
30. §4: F8's note column: "bundle and replay 0.5; evidence and v2 wiring 0.6; decision records with TX 0.7".

## From the W1 P3 review (`docs/reviews/W1-P3-review.md`, 2026-11-06)

31. §3 F7 exit (`target-architecture.md:875–876`): the same replacement as ADR 0066 E-F7-4: "An index-1 probe is
    accepted; Q5.A13 (a)–(f): (f) α ≡ κ ≡ 0 refused `dae_index_unsupported` naming the volume row; (c), (d) carry
    `dae_index_near_singular`; (e) (thermally expanding, κ ≡ 0) and a `cubic.pr-v1` liquid are regular" (review M6).
32. §2.4 routing: `phase_routing` gains `vapor: <port> | null` beside `light_to_heavy` (the liquid ports) and `solids`;
    VAPOR, or a lone `vapour_like` FLUID (Q4.R9), goes to `vapor`, else to the first liquid port when `vapor` is null;
    LIQUID slots go over `light_to_heavy` by density; two or more active FLUID phases by SQ-F6-5's default (ADR 0065 D9,
    review M4).
33. §2.4 identity: the v2 structure document's `sources` gain the role `configuration` (`document_sha256` of the v2
    revision with every pinned numeric value removed), and the v2 label is `FSR2-<configuration_sha256[:12]>` (ADR 0065
    D3, review M1).
