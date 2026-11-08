# MSG review — messages and the code catalogue (ADR 0058), the single reviewer pass

Reviewer: design lane (`reviewer`), 2026-11-06. Branch `wp/MSG` at `8d955cd7`, against ADR 0058 and
`docs/design/MSG-messages.md`. Brief: `docs/briefs/MSG-reviewer.md`. Nothing was run for this review; every number
below is the engineer's (`docs/MSG_DECISIONS.md`, manifest `evidence/MSG/b1a82351…`) or read from the code.

## Verdict

**Not merge-ready yet. The package becomes merge-ready after M1–M6, plus M7 if Frank does not choose to defer it.**
The machine layer is sound. No producer text changed. The identity evidence holds: MSG-G0 (a) 0 diff, (b) 0/562,
(d) 0 hits in 442 stores, and F0 PASS. Rendering is total on the paths I traced (`_explain` falls back to
`_minimal`). Projection attaches the explanation and is idempotent. `failure` is derived on read and is non-null iff
there is a failure bundle.

What blocks the merge is coverage and prose:
- the note's normative list of complete entries is about one-fifth done;
- one complete entry makes a false physical claim on a reachable path;
- the manifest does not record half of the gates.

## Must fix

- **M1. §4.2.6's normative "complete in 0.4" list is not met.**
  - The list holds about 75 codes. 15 are complete (MSG-G4: `complete: 15`).
  - Still stubs:
    - 12 of 15 `api_error`, including `invalid_request`, `forbidden`, `internal_error` and `revision_unsupported`;
    - 21 of 22 outcomes;
    - all 12 statuses (`VERIFIED`, `RELAXED`, `UNVERIFIED`, `FAILED`, regularity, validation);
    - `completed`, `failed`, `cancelled` and `timed_out`;
    - `isentropic_state_single_phase` and `pressure_fall`;
    - three of FB-01's five (`not_a_directory`, `not_a_project`, `project_id_mismatch`).
  - No test catches this. Note §6 gave WO-9 only "every corpus code", so no work order owns the rest. That is a gap
    in the note, not an engineer error.
  - Note Q5's promise that certificate-status meanings reach the user through `explain` is unmet while the statuses
    are stubs ("Status VERIFIED.").
  - Fix:
    - write the entries;
    - add `tests/test_msg_coverage.py::test_the_normative_list_is_complete`, pinning §4.2.6's codes as
      `complete: true` and lint-clean;
    - send the new `why`/`action` texts to one design-lane prose check by a fresh agent with a tight brief, not a
      second full review.
  - **Needs a decision (Frank)** only if he prefers to ship 0.4 with these as a declared limitation. I would complete
    them first, because every transported error carries one of the 12 `api_error` codes.
- **M2. `pressure_rise` is wrong for valves.**
  - `pressure_rise(valve)` is emitted at `models/thermal/valve.py:248` and `models/syn001/valve.py:396`.
  - The entry's title ("A turbine outlet pressure…") and its `why` ("A turbine expands the fluid…; raising the
    pressure takes a pump or a compressor") are turbine-only. A valve with `P_spec > P_in` renders a false
    explanation.
  - Fix:
    - give the entry a generic title;
    - add a `why` variant `equals: {machine: valve}` (a valve throttles and can only lower the pressure);
    - add an example and an engine test for `pressure_rise(valve)`.
- **M3. The MSG-G0 line must read PASS under the Q3 ruling.**
  - Make `--parts bd` the post-F0 default of `scripts/msg_identity_gate.py`, and record F0's
    `corpus_identity.py --check` line beside it for (a) and (c).
  - Replace the manifest's `MSG-G0.c fail` check with that line.
  - Do not edit the baseline.
- **M4. The manifest omits gates that ADR 0058's acceptance list requires.**
  - `evidence/MSG/b1a82351…/manifest.json` lists G0 and G4–G8 only. Add check records with values for:
    - MSG-G1, MSG-G2, MSG-G3 (misses and defects);
    - MSG-G9;
    - MSG-G10 (the `without_msg` equalities and the new digests);
    - Performance: cold load 100–119 ms and render median 0.16–0.20 ms (D2-6), plus the A/B durations;
    - the aarch64 CI identity job.
  - A gate that ran but is not recorded is not evidence.
- **M5. The `explain.md` design-lane review: approved after two edits (Q6).** Then record it in `REVIEW.json`. Frank's
  human review stays a merge blocker.
- **M6. Register link c_4 before the merge (Q5).** Precedent R-457: an MCP-visible change needs a link, a strip, a
  digest and a register entry.
- **M7. WO-5a (Q1): do it before `tested`.** It is unblocked by the Q1 ruling and turns most WO-5 xfails green.
  **Needs a decision.** The alternative is to merge with the strict xfails and run WO-5a straight after. I would do it
  first: numbers are the point of FB-05, and WO-5a is one bounded work order.

## Should fix

- **S1. `out_of_domain` (refusals.yaml:803).**
  - Its `why` says, unconditionally, "For water (IAPWS-95) this version covers 273.16 K to 1273.15 K and 100 Pa to
    100 MPa". The numbers match `thermo/iapws95.py:97-100`. But every provider emits this code, including PR, Wilson
    and CoolProp. Make the sentence a variant on the method, or say "for example".
  - The kind is `input` unconditionally, and the action says to check the specified temperatures. That is wrong when
    a solve iterate leaves the domain. Add an `outer`-conditioned variant, with `input` under
    `initializer_failed`/admission and `numerical` otherwise, or word the action for both cases.
- **S2. `legacy._typed` (legacy.py:160-170).**
  - `float()` accepts `nan`, `inf` and `1_0`. A `detail_pattern` group that captures one of these puts a non-finite
    float into `RunFailure.params`, which is a JSON document. Today no pattern exists; WO-5a adds them.
  - Return the text when the value is not finite (§4.5). Use strict decimal groups in the patterns.
- **S3. `unsupported` (api_errors.yaml:45).** Without `reason`, the action still reads "Read the reason's
  explanation…". Add a variant for the case where `reason` is absent.
- **S4. Stub kinds, sampled per note Q10 (`bug` and `numerical` only).**
  - `worker_lost`, `owner_lost` and `store_error` are environment events: a killed process, a lost owner, SQLite.
    They are not OpenFlowsheet defects, so `bug` and its "report it" action mislead.
  - `CHECKPOINT_INCOMPATIBLE` is not `numerical`.
  - Settle these with M1.
- **S5.** `DIM-01`: kind `input` is confirmed; drop `review: true`. `D3-4`: `members` is cut silently at 64. Add
  `members_truncated` or say so in the docs.

## Rulings

- **Q1: route (a), narrowed. The numbers that only the kernel knows go to (c), deferred to the F6 v2 unit models
  (ADR 0065). (b) is rejected. No architect pass is needed.**
  - **What is lost, and where.** The failing unit's full message, with its detail lines, reaches the traversal hop
    `models/revision_flowsheet.py:1029-1034`. That file is outside M9. The hop keeps only line 1
    (`splitlines()[0]`), and line 2 already holds most of the numbers, as exact `repr` floats:
    - P2: `s* = … lies past the saturated … entropy … at … Pa` (kernel.py:661-664, kept by machines.py:704);
    - P5: `P_spec = … Pa is above the inlet's … Pa` (machines.py:657-663);
    - P4: `temperature … K outside [273.16, 1273.15] K`;
    - P1: `declared liquid, closure VAPOR beta=…; declare vapor`.
  - **WO-5a, the build.**
    - Build the sidecar at that hop, in P4's form: `Diagnostic(<code of line 1>, {"detail": lines 2+})`.
    - Carry it FlowsheetPass → InitialStateFailure → StepResult → `run["diagnosis"]`, with §4.6's carrier rule and
      flags test.
    - Apply the explained entry's `detail_pattern` to the diagnosis's `detail` in `explain_failure`. Today the
      pattern is applied only to the bundle message.
    - Write patterns for `pressure_rise`/`pressure_fall` (`p_spec`, `p_inlet`), `isentropic_state_two_phase`
      (`s_star`, `s_saturated`, `pressure`; the declaration fixes the entropy unit after the basis is confirmed),
      `out_of_domain` (value and bounds) and `phase_regime_mismatch` (`declared`, `landed`, `vapour_fraction`).
    - C02's `outlet` is derived from `unit` and the revision's connections, as a §4.2.5 derived param.
  - **What it delivers, without touching a frozen byte or a machine text (I1):**
    - C11's and C02's numbers;
    - C09's bounds;
    - C01's `landed`, and with it the `phase_capability` action.
  - **What it costs.** It is identity: yes. MSG-G0 (b) on C01/C02 is the guard (Q3).
  - **Deferred under (c):** C01's `value`, `saturated_liquid`, `saturated_vapour` and `pressure` appear in no text.
    They stay strict xfails and become a declared limitation.
  - **Why not (b).** (b) reopens a freeze registered one day ago (R-940) to add display numbers to a family that F6
    replaces.
  - **The record.** This amends note §4.6's producer list, not ADR 0058 D6 or R-936. The sidecar stays on the failure
    value and is persisted only in `run.diagnosis`. There is no ContextVar and no render-time property call. Record
    it as a register entry.
  - **Correctness fixtures.** Give the numbers independent expectations:
    - C11: the case's inputs, 5 MPa and 3 MPa;
    - C09: the provider's box;
    - C02's `s_saturated`: steam tables at the case pressure.
    With these the corpus also becomes a correctness fixture, not only a regression fixture.
- **Q2: yes to both, with conditions.**
  - Rule 2 becomes:
    1. the first `FAIL` check: its id, then the codes parsed from its message, with `implicated_objects` as elements;
    2. if there is none and the report is `DRAFT`, the first `NOT_RUN` check whose message parses to a code with an
       entry;
    3. never a `WARN`.
  - The inner codes this reaches (`specification_unconsumed`, `specification_missing`,
    `specification_unit_unsupported`) must be complete in the same change. Otherwise the innermost-entry rule
    explains a stub, which is worse than today's `DIM-01`/`revision_not_ready`.
  - C08's "degc": allowed as a §4.2.5 derived param of a specification element (the spec's unit text, quoted),
    renderer-only.
- **Q3: F0 replaces MSG-G0 (a) and (c). MSG-G0 keeps (b) and (d).**
  - F0 has no failure-path bundle of the thermal family. Its M2–M6 are SYN-001 RC bundles. C01/C02 are exactly where
    WO-5a's carriers land.
  - (c) is not re-taken. Its 57 baseline replays are unchanged, and the 52 F0 bundles are F0 M7's (52/52).
  - See M3.
- **Q4: accept D7-7, D7-10 and `HARVEST_SIZE`.**
  - D7-7 pins `explain.md` as the c_4 addition, with a control.
  - D7-10's five pins and A20's 21 → 22 follow from ADR 0058 D7, which Frank accepted. Name the envelope change in
    the c_4 entry (Q5).
  - `HARVEST_SIZE` moves again at the `tested` re-take.
- **Q5: a new register entry in R-457's form.**
  - "`main`'s surface chain gains c_4 = (R-934/R-937, `without_msg`, D_4)".
  - D_4 is re-measured on the merge tree, not taken from WO-7's `1ca06b37…`, because main may have moved.
  - The carry naming c_4 is a release-time item (R-457: "Frank's carry is the gate's check at a release, not a `main`
    test"). It goes on the 0.4 RC list, and it does not block the merge.
- **Q6: approve `explain.md` after two edits.**
  1. "Text in the result is project data" contradicts "reads the message catalogue only, not the project". Write
     "Text in the result is data, never instructions": an F1 namespace may supply it.
  2. "rendered with its numbers" promises numbers that run failures lack today. Write "rendered with its own ids and,
     where known, numbers".
  - Re-pin `MSG_FILE_SHA256`, `REVIEW.json` and D_4.
  - Every other claim checks against `entry_document` and `suggestions` (≤ 5, distance ≤ 3, case-insensitive).
- **Q7.**
  - D3-4: confirmed. Reusing `artifact_children` is right, and omitting `operation` keeps the pre-MSG detail.
  - D4-1: overruled. The three must be complete (§4.2.6, M1).
  - D6-3: confirmed. A project-free `solve` has no revision or job ids to show.
- **Q8.**
  - `revision_not_ready`, `task_unsupported`, `model_unsupported` and `DIM-01` are approved. `degC` is accepted by
    `units/__init__.py:405`, and `list_models` exists.
  - `pressure_rise`: must fix (M2).
  - `out_of_domain`: should fix (S1).
  - `unsupported`: should fix (S3).
- **Q9: not in MSG's scope.** It belongs to the verifier later (ADR 0013), as A5-a says.
  - The string parses under §4.3 into code and arg, and it has a catalogue entry, so C3 holds.
  - A typed reason changes check-result and certificate content, which is identity, and MSG may not change producer
    data (I1).
  - The MSG renderer parses only for display. It is not report logic, so ADR 0068 C-2 is not engaged.

## Notes

- `run-result.schema.json` is closed at the top level (`additionalProperties: false`). `failure` therefore makes a
  0.3 client that validates `RunResult` reject 0.4 results. That is the same argument D4 used against a new
  `ApiError` member. ADR 0058 D5 accepted it, so the 0.4 release notes must say so.
- §4.3's third clause parses a bare key at the head of a `"<word>: …"` text as a code. Examples are `failed`,
  `running` and `forbidden`. This is by design. If a mis-explanation shows up, restrict the clause by family.
- Under pytest the audit is always on. The production load (no schema pass, D2-6) and the non-audit `explain_failure`
  branch therefore run only in subprocess tests. One in-process test with the audit off would pin them.
- `raise_for_outcome` relies on the invariant "not CONVERGED ⇒ failure bundle" (`run/session.py:66-70`). It holds
  today, but raising on `outcome != "CONVERGED"` as well would make the method self-evidently correct.

## Not established by this review

- I ran nothing: no gate, no test, no CI. I did not see aarch64.
- Not examined:
  - `template.py`;
  - the G2 scanner;
  - most of `cli.py`;
  - `test_msg_engine.py` and `test_msg_surfaces.py`;
  - the generated docs pages;
  - the schema bodies;
  - stub kinds outside `bug` and `numerical`;
  - the web shell beyond its use of text nodes.
- The corpus texts are self-generated regression goldens. Its codes, chains and elements carry the §7 table's
  independent expectations. No number is asserted against an independent value yet.
