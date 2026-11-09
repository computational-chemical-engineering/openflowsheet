# MSG catalogue prose ruling: X02's and OPT's new codes; OPT D-93 (corpus case C12)

Design lane (`specifier`), 2026-11-09. Brief: `docs/briefs/MSG-catalogue-prose-X02-OPT.md`. Base: `main` at `c1ced8a7`
(X02 and OPT merged). Nothing was run except a scratch harness, described in §6.

## 1. Authority and scope

This note is the design lane's prose and kind ruling for the catalogue entries that X02 (D-39) and OPT (D-92) added,
and the ruling on OPT D-93 (corpus case C12). MSG design note §4.2.6 says the build lane drafts complete entries and
the design lane judges them, because no test catches a wrong physical claim. This note does that judging. The
build lane applies the ruling as written (§5).

The note is consistent with:

- **ADR 0058 and the MSG design note:** I1 (no machine message changes), I2/I3 (no identity changes), I8 (no claim
  that a solution does not exist), §4.2.1 (kinds), §4.2.2 (fields), §4.2.7 (G4 lint) and §3.6 (the corpus rule).
- **ADR 0070 D1:** the warm-start admission refusals.
- **ADR 0071:** D8, D10 and R-968 (validate for optimisation; `nlp_solver_unavailable`).
- **The OPT design note:** §4.2.3, §4.5, §4.7 and §4.11.

Nothing in the frozen interfaces (`docs/interfaces-frozen.md`) or in any schema changes. The catalogue digest is
outside every identity (MSG §3.2), so its change is not a frozen-surface change.

**House style.** The MSG note has no section titled "house style". This ruling takes the style to be the following
rules, each with its source:

- **S1 (the summary).** Line 1 says what failed and where, in the user's ids. Complete entries keep it to 200
  characters or fewer and pass the jargon lint (note §1, §4.2.7).
- **S2 (why and action).** The why states the rule, with the numbers where they exist. The action says what to do.
  Both are written in plain words for a student (note §1, FB-05).
- **S3 (the title).** A plain noun phrase of 80 characters or fewer (§4.2.2).
- **S4 (quoting).** Element ids are single-quoted, as the renderer does it (§4.2.4). Literal values go in double
  quotes, e.g. `"simulation"`. There are no Markdown backticks: the text renders verbatim in the CLI and in Python
  (§4.5), and no other entry uses them.
- **S5 (spelling).** Prose uses British spelling, as the catalogue already does ("vapour", "optimise"). Machine
  values are written exactly: the task `"optimization"`, route ids.
- **S6 (I8).** No text says or implies that no solution exists.
- **S7 (stubs).**
  - The kind follows §4.2.1's rule.
  - The summary is one sentence, written from the emission site (WO-2). There is no why and no action.
  - `review: true` marks a kind assignment that awaits a ruling (§4.2.2). It never marks prose.

## 2. What this ruling establishes (summary)

"Review after" is the value of the `review` flag once the ruling is applied. "absent" means the line is removed or
was never there.

| Code | Ruling | Kind (final) | Review after |
| --- | --- | --- | --- |
| `warm_start_source_missing` (X02) | keep | input | absent (was absent) |
| `warm_start_unit_unknown` (X02) | rewrite `why` | input | absent (was absent) |
| `coupling_warm_start` (allow-list) | keep allow-listed; reword the reason | — | — |
| `nlp_solver_unavailable` (OPT) | rewrite `why`, `action`, `gap` | not_supported | absent |
| `request_invalid` (OPT) | rewrite: arg renamed `member`, empty-member variant, `detail` param | input | absent |
| `DECISION_NOT_CONTINUOUS` | stub kept; title and summary rewritten | input | absent |
| `DECISION_UNIT_NOT_INTERNAL` | stub kept; title and summary rewritten | input | absent |
| `REVISION_MISMATCH` | stub kept; title and summary rewritten | input | absent |
| `REVISION_UNBOUND` | stub kept; title and summary rewritten | input | absent |
| `TOO_MANY_STARTS` | stub kept; title and summary rewritten (the old title was wrong) | input | absent |
| `OPTIMIZATION_ROUTE_UNAVAILABLE` | stub kept; title and summary rewritten | not_supported | absent |
| `REGIME_MARGIN_UNDEFINED` | stub kept; title and summary rewritten | not_supported | absent |
| `k03_kind_bound`, `no_declared_bound` (allow-list) | keep allow-listed; correct the reason (it names a function that does not exist) | — | — |
| `phase_row_not_closure_test` (allow-list) | keep, reason unchanged | — | — |
| `L-OPT-2` (limitation) | keep the G4 rewording; drop the internal-process sentence | notice | — |
| `task_unsupported` (raised by the C12 ruling, §4) | rewrite: its prose has been false since ADR 0071 | not_supported | absent |
| C12 (D-93) | keep `nlp_solver_unavailable`, made independent of the install; `gap.limitation` L-OPT-1 | — | — |

The brief says all of these entries are flagged `review: true`. X02's two entries were never flagged. D-39 left them
unflagged because their kinds follow the `*_missing` and `*_unknown` rows of the rule table, and §4.2.2 agrees. Of
OPT's entries, only `nlp_solver_unavailable` and the readiness stubs needed a judgment, because no row of the table
matches them. `request_invalid` matches the `*_invalid` row, so it never needed the flag. This ruling settles every
kind above, so the count of `review: true` drops from 138 to 129.

## 3. Rulings per code, with the YAML to apply

Each block below replaces the whole entry of that `code` in `src/openflowsheet/messages/catalogue/refusals.yaml`, in
place. Keep the 2-space indentation under `entries:` and leave the surrounding comments where they are. The values
must be applied **verbatim**: §6's digest is computed over them.

### 3.1 X02

**`warm_start_source_missing`: keep.** The entry is correct against `admission.py:200-212` and
`store.py:1170-1188`:

- the job must be a `solve` job of this project holding a `solution_state` artifact;
- its certificate status does not matter.

The title, summary, why and action are plain, and they follow S1–S4. The param is named `job_id`, which keeps it
clear of the context param `job` (§4.2.5).

**`warm_start_unit_unknown`: rewrite `why`.** The old why said "coupled on the bound route". Both terms are internal
binder vocabulary that a student cannot act on (S2). What the sentence means (X02 note §1, `admission.py:203-206`):

- a coupling start is the outer iterate of a unit that an external program computes;
- whether a unit is such a unit is the run's compatibility check, which records a failing start and does not refuse
  it.

The title, summary, action and example are unchanged.

```yaml
  - code: warm_start_unit_unknown
    family: refusal
    kind: input
    complete: true
    title: A coupling start for a unit the revision does not have
    args: [unit]
    params: {unit: {type: text, label: unit}}
    summary: "The declared warm start gives a coupling start for '{unit!raw}', which is not a unit of this revision."
    why: "A warm start may give, for each unit computed by an external program, starting values for what the flowsheet and that program exchange (the coupling), keyed by the unit's instance id; so each key must be a unit of the revision being solved. Whether the unit is computed by an external program in this solve is checked when the run starts; a start that fails that check is recorded as rejected, not refused."
    action: "Key each coupling start by the instance id of a unit in this revision, or remove the key '{unit!raw}'."
    examples:
      - chain: [invalid_request, warm_start_unit_unknown]
        params: {unit: R9, pointer: /body/warm_start/coupling/R9}
```

### 3.2 OPT, complete entries

**`nlp_solver_unavailable`: rewrite `why`, `action` and `gap`. The kind is `not_supported` (final).**

- **Defect: backticks (S4).** "the \`nlp\` environment" renders with literal backticks. C12's golden text shows them
  today.
- **Defect: the gap.** `gap.limitation` was null. The support matrix's L-OPT-1 is exactly the declared limitation
  ("runs only … in the audited nlp environment on linux-x86_64"), and `gap` is what R-931's agentic layer reads, so
  it now names L-OPT-1.
- **Kind.** The rule table has no `*_unavailable` row. The refusal reports an install or platform the audit does not
  cover (`closure.py:233-263`): the extra is absent, the platform is not audited, the verdict is not `PASS`, or the
  licences are not accepted. None of these is an error in the flowsheet, so the kind is `not_supported`.

The summary is unchanged. C12's `in_summary: [optimise]` and `action_token: nlp` still hold.

```yaml
  - code: nlp_solver_unavailable
    family: refusal
    kind: not_supported
    complete: true
    title: Optimisation without the audited NLP solver
    summary: "This installation cannot optimise: the audited NLP solver is not available here."
    why: "Optimisation solves with Ipopt, reached through Pyomo and cyipopt, in the versions whose licences and binaries were audited: the nlp extra's audited environment on Linux x86-64. Without it this version refuses to optimise rather than run an unaudited solver."
    action: "To optimise, use the audited nlp environment on Linux x86-64 (user guide, section \"The nlp extra\"); to check the revision for a solve, validate it with the task \"simulation\"."
    gap: {limitation: L-OPT-1, capability: "optimisation outside the audited nlp environment on Linux x86-64"}
    see_also: [unsupported]
    examples:
      - chain: [unsupported, nlp_solver_unavailable]
        params: {}
```

**`request_invalid`: rewrite. The kind is `input` (final, by the `*_invalid` row).**

**Defect 1: the location in the summary was wrong.** The param was named `pointer`, the same name as the `detail`
member `pointer` that both producers set. `render._merge` (`render.py:541-551`) lets a `detail` member win over a
legacy arg, so the summary showed the envelope pointer, not the member's place in the optimisation request:

- `cli.py:180` sets `/request` + p, which reads as "The optimisation request is invalid at /request/objective/kind".
  The user's request file has no `/request` root.
- `jobs/runner.py:1069` sets `/body/request` + p.

**The fix.** Rename the arg to `member`. The summary then shows p itself, the place inside the optimisation request.
The machine `detail.pointer` is untouched (I1).

**Defect 2: the empty arg.** `request_problems` returns `""` for a problem at the root of the request. The arg is then
the empty string (`request_invalid(): …`), and the old summary read "invalid at ." The fix is an empty-member variant,
in `invalid_request`'s form (`api_errors.yaml:97-100`).

**The check's message.** The why now shows the check's own message through the `detail` text param. This is the
`out_of_domain` precedent (`refusals.yaml:896-902`). The why also loses the cryptic "the detail after the code".

```yaml
  - code: request_invalid
    family: refusal
    kind: input
    complete: true
    title: An optimisation request that breaks its schema or rules
    args: [member]
    params:
      member: {type: pointer, label: member}
      detail: {type: text, optional: true, label: the check's message}
    summary: "The optimisation request is invalid."
    why: "Before anything is solved, an optimisation request (its decisions and their bounds, the objective, the constraints and the starts) is checked against its schema and the rules stated for its members, and this one breaks one of them.[ The check reported: {detail!raw}.]"
    action: "Correct the request as the check reports, and send it again."
    variants:
      # An empty member is the whole request (`request_problems` at the root).
      - when: {has: [member], not_equals: {member: ""}}
        summary: "The optimisation request is invalid at {member}."
        action: "Correct the member at {member} as the check reports, and send the request again."
    examples:
      - chain: [invalid_request, request_invalid]
        params: {member: /decisions/0/upper, detail: "'high' is not of type 'number'"}
      - chain: [invalid_request, request_invalid]
        params: {member: "", detail: "'decisions' is a required property"}
```

### 3.3 OPT, readiness stubs: kept as stubs, titles and summaries rewritten, kinds final

**They stay stubs, and that is permitted.**

- None of these seven codes is on §4.2.6's normative list of entries that must be complete.
- No rendering path reaches them today:
  - Validation checks carry the ids `OPT.<CODE>`, which have no entry. A core entry cannot hold a `.`
    (`catalogue.py:306-307`), so the CLI's `_check_line` (`cli.py:115-125`) prints nothing under such a check.
  - Optimisation reports are never rendered (MSG §3.3).
  - So the only places a user sees these entries are `explain <CODE>` and the docs page.
- MSG review Q2 requires an entry to be complete when a rendering reaches it. That trigger is absent here. §8 F1
  covers the day it appears.

**But the summaries must say something.** The WO-2 placeholder ("Refused: too many starts.") tells the student who
types `explain` nothing. Worse, `TOO_MANY_STARTS` fires for **zero** starts as well: the schema allows
`include_revision: false`, no explicit starts and `halton: 0` (`request.py:252-253`, `:481-485`). So "Too many starts"
is wrong as a title. Each summary below is written from its emission site (S7). Its kind is ruled, and its review
flag is removed.

- **`DECISION_NOT_CONTINUOUS`** (`revision_host.py:249-282`). The decision is probed at the ends of its bounds. It
  fails if the flowsheet does not bind there, its structure changes, it moves no parameter or more than one, the
  parameter is not set to the probe value, or the parameter is already another decision's. **Kind `input`:** the
  user picks another specification or narrower bounds.
- **`DECISION_UNIT_NOT_INTERNAL`** (`revision_host.py:237-247`). The bounds are not in the SI unit of the kind, or the
  kind has no SI unit. **Kind `input`.**
- **`REVISION_MISMATCH`** (`request.py:458-466`). The request's `revision_sha256` differs from the stored revision.
  **Kind `input`, not `bug`.** The `*_mismatch` row is for *internal* mismatches (§4.2.1). Here a value the user
  supplied disagrees with the revision.
- **`REVISION_UNBOUND`** (`request.py:524-571`). Binding refused, or the decision probes raised
  `RevisionUnboundError`. **Kind `input`.**
  - Three of the four binder refusal kinds map to `input` by MSG's own `revision_unsupported` variant (§4.2.1).
  - The stub declares no args, so the parenthesised inner code is not parsed as a chain link. The kind is therefore
    only ever shown by `explain`, generically. §8 F1 says what changes when the code is completed.
- **`TOO_MANY_STARTS`** (`request.py:481-485`). **Kind `input`.**
- **`OPTIMIZATION_ROUTE_UNAVAILABLE`** (`request.py:535-545`). The revision solves on a route other than
  `revision_eo`: a coupled or sequential-modular flowsheet, or `legacy_eo` (guide `optimisation.md:18-20`). **Kind
  `not_supported`** (L-OPT-1). The title does not say "one system of equations", because `legacy_eo` is also
  equation-oriented. The summary names the route.
- **`REGIME_MARGIN_UNDEFINED`** (`phase.py:22-30`, `revision.py:265-270`). A held split has no margin, or a declared
  port's saturation temperature is undefined at the start, so no phase row can hold the regime and the start fails.
  **Kind `not_supported`:** the cause is a gap in what the optimiser formulates (OPT §4.7), not an error in the
  flowsheet. The summary avoids the linted word "regime", so it stays lint-clean if it is ever completed.

```yaml
  - code: DECISION_NOT_CONTINUOUS
    family: refusal
    kind: input
    complete: false
    title: A decision that is not one continuous parameter
    summary: 'A decision of the optimisation request does not set exactly one flowsheet parameter of its own across its bounds, so it cannot be varied continuously.'
  - code: DECISION_UNIT_NOT_INTERNAL
    family: refusal
    kind: input
    complete: false
    title: Decision bounds not in the SI unit of their quantity
    summary: 'The bounds of a decision in the optimisation request are not given in the SI unit of its specification''s quantity, the only unit the request accepts for them.'
  - code: REVISION_MISMATCH
    family: refusal
    kind: input
    complete: false
    title: An optimisation request written for another revision
    summary: 'The optimisation request names, by its SHA-256, a revision other than the one being optimised.'
  - code: REVISION_UNBOUND
    family: refusal
    kind: input
    complete: false
    title: A revision that cannot be set up for optimisation
    summary: 'The revision could not be set up as a flowsheet to solve, so it cannot be optimised; the code in parentheses names the reason.'
  - code: TOO_MANY_STARTS
    family: refusal
    kind: input
    complete: false
    title: A start count outside 1 to 32
    summary: 'The optimisation request asks for no start or for more than 32; a request has 1 to 32 starts in all, counting the revision''s own values, the explicit starts and the Halton points.'
  - code: OPTIMIZATION_ROUTE_UNAVAILABLE
    family: refusal
    kind: not_supported
    complete: false
    title: A revision not on the route optimisation needs
    summary: 'This version optimises only a revision that solves on the revision_eo route, as one system of equations; this revision solves on another route, which the message names.'
  - code: REGIME_MARGIN_UNDEFINED
    family: refusal
    kind: not_supported
    complete: false
    title: A start at which a unit's distance from a phase change is undefined
    summary: 'At this start the optimiser cannot measure how far a unit is from changing phase, so it cannot hold that unit in its phase and cannot use this start.'
```

Each block replaces its entry where it already stands; the entries are in alphabetical order in that block, so they
are not moved together.

### 3.4 The allow-list (`scan-allow.yaml`): every reason checked

The test was: no code path passes the label to a renderer or to a G3 audit hook. The hooks are `api_error()`,
`bundle_for()`, `Unbound` and `RunUnsupportedError`.

**The executable evidence.** G3 does not consult the allow-list (`audit.py:26-36`). So if any of these labels had
reached a hook on a path the suite exercises, OPT's merge CI (`42534167073`) would have failed.

- **`coupling_warm_start`.** Never rendered. It is the `message` of a trace `initializer_candidate` solve event
  (`coupled_run.py:940-958`, `:1102`), and solve events gain no explanation (MSG §3.3). Allow-listing it agrees with
  its twins `compatible_warm_start(…)` and `warm_start_rejected(…)`: both are built from constants and have no
  entry. X02 note §5.9 proposed a `notice` entry. That is rightly not taken, because the `notice` family is for
  result flags (MSG §3.3).
  - **The reason is reworded.** It said "never a message", but the label *is* a solve-event message. What is true is
    that nothing renders it.
- **`k03_kind_bound`, `no_declared_bound`.** Never rendered. They are bound-reason labels that
  `RevisionNlpHost.bounds` writes (`revision_host.py:794-821`, beside `provider_domain` and `nonnegative_flow`). They
  land in the optimisation report's `formulation.bounds.<name>.reason` (`formulation.py:804-807`,
  `closure.py:856`). No optimisation report is rendered.
  - **The reason is corrected.** It names `variable_bounds`, which does not exist in `revision_host.py`, and it says
    "optimizer record".
- **`phase_row_not_closure_test`.** Never rendered. It is a V4 detail list (`verification.py:730-733`, `_regimes`)
  inside the candidate verification of the report. **Keep it**, reason unchanged. It sits beside
  `PHASE_REGIME_CHANGED(…)`, which has no entry either.

The new lines for `src/openflowsheet/messages/catalogue/scan-allow.yaml` (keys unchanged; one line each):

```yaml
  coupling_warm_start: "the message of a trace `initializer_candidate` solve event (application/coupled_run.py `solve_coupled`; X02 note §5.9); solve events gain no explanation (MSG note §3.3), so nothing renders it; its twins `compatible_warm_start(…)` and `warm_start_rejected(…)` are built from constants and have no entry either"
  k03_kind_bound: "a variable-bound reason label (studies/nlp/revision_host.py `RevisionNlpHost.bounds`, OPT design §4.2.3) in the optimisation report's `formulation.bounds.<name>.reason`; no optimisation report is rendered (MSG note §3.3), so nothing renders it"
  no_declared_bound: "a variable-bound reason label (studies/nlp/revision_host.py `RevisionNlpHost.bounds`, OPT design §4.2.3) in the optimisation report's `formulation.bounds.<name>.reason`; no optimisation report is rendered (MSG note §3.3), so nothing renders it"
```

### 3.5 L-OPT-2

**Keep the G4 rewording.** "650 K, a start that violates the constraint" replaced "on the infeasible side". It is
accurate: D-70 has W = 15411 W < W_min at 650 K. It no longer trips I8, and "feasible region" alone is not linted.

**Drop the last sentence.** "Whether the options change is a design-lane question (OPT_DECISIONS D-70)." is internal
process talk in a user-facing limitation, and no other row of the matrix has any. The row's `evidence` already
links `docs/OPT_DECISIONS.md`.

The change is made at the source: in `benchmarks/t08/support_envelope.yaml`, the last folded line of L-OPT-2's
`text` becomes

```yaml
      the remedy.
```

(it read `the remedy. Whether the options change is a design-lane question (OPT_DECISIONS D-70).`). Nothing else in
the row changes.

## 4. C12 (OPT D-93): the ruling

**Ruling: C12 keeps D-93's re-pointing to `nlp_solver_unavailable`, with two amendments.**

**Why keep the re-pointing.**

- **It follows MSG §3.6's own rule.** A case registers a mistake and records the code that the software actually
  emits for it. C12's registered mistake is `validate --task optimization`. On the default install that call now
  emits `unsupported`/`nlp_solver_unavailable` (ADR 0071 D8, R-968). That is the refusal every student on the
  default install meets when they first try optimisation, so it is the case the corpus exists to pin.
- **It keeps the path the row was registered for.** The chain is an `ApiError` `unsupported` wrapping a typed
  reason, of kind `not_supported`, with a typed `gap`, rendered on all four transports. The pin is now on the new
  entry's prose.

**Rejected alternative: re-point C12 at `commit_change`/`preview_change` with `task: "optimization"`.** That call still
emits `task_unsupported(optimization)` (`local.py:1792-1799`). It is rejected for three reasons:

- It pins a refusal that a beginner hardly ever meets: `task` is a change-set member nobody sets by accident.
- `task_unsupported`'s machine path is already covered by `test_t08_w2_unsupported.py`'s U05 change-path test.
- Its prose was false after ADR 0071. That is a defect in the entry, which is corrected below, not a reason to keep
  a weak case.

**Amendment 1: make the case independent of the install. This is a defect in D-93 as merged.**

- `_c12` calls `validate(revision, "optimization")` with no request.
- Where an audited solver *is* installed, the probe passes, and the same call emits `invalid_request` "task
  optimization needs an optimization request" (`local.py:528-546`). C12 would then fail.
- Today the audited environment runs only `-m nlp` (`scripts/m03_nlp_check.sh:56-57`), so the failure is latent. But
  a corpus case must not depend on which extras the machine has.

**The fix.** Every C12 test node runs with `openflowsheet.studies.nlp.closure.audited_solver` replaced, through
pytest's `monkeypatch`, by a function returning an unavailable `SolverAvailability`. This covers the setup and the
four-transport node, and all four transports run in-process (`tests/t07_transport_support.py`), so one patch covers
them all.

- **Use the existing double:** `UNAVAILABLE = SolverAvailability(False, "test double: no audited solver")`,
  `tests/test_opt_request.py:52`.
- **Precedent:** `tests/test_opt_cli.py:30` patches `closure.audited_solver` the same way.
- **The output does not depend on the double's text.** The machine message carries no probe detail (D-16:
  `validation.py:175-182`).
- **No C12 node may skip.**

**Amendment 2: the case records the new gap.** In `tests/fixtures/msg/corpus.yaml`, C12 gets
`gap: {limitation: L-OPT-1, capability: true}`. Its `text` is regenerated, and the diff must be only the `Why:` and
`Do:` lines. The `mistake`, `code`, `kind`, `chain`, `in_summary`, `elements`, `numbers` and `action_token` fields are
unchanged.

The expected `Why:` and `Do:` lines, the same on the Python and CLI surfaces, are:

```
  Why:     Optimisation solves with Ipopt, reached through Pyomo and cyipopt, in the versions whose licences and binaries were audited: the nlp extra's audited environment on Linux x86-64. Without it this version refuses to optimise rather than run an unaudited solver.
  Do:      To optimise, use the audited nlp environment on Linux x86-64 (user guide, section "The nlp extra"); to check the revision for a solve, validate it with the task "simulation".
```

**What the C12 ruling forces on `task_unsupported`: rewrite (complete entry, kind `not_supported` final).** The
refusal survives only on `commit_change` and `preview_change` (`local.py:1792-1799`; U05 change path). Its present
prose is false:

- it says the version "validates for simulation only";
- it says the version "checks none" of an optimisation formulation.

Both statements were superseded by ADR 0071 (R-968). The true reason for the remaining refusal: a change set has no
`optimization` member (`change-set.schema.json`), while validating for optimisation needs a request (OPT §4.11). The
summary passes the jargon lint.

```yaml
  - code: task_unsupported
    family: refusal
    kind: not_supported
    complete: true
    title: A change checked for a task other than simulation
    args: [task]
    params: {task: {type: text, label: task}}
    summary: "A change is checked for the task \"simulation\" only; this version cannot check it for the \"{task!raw}\" task."
    why: "Committing or previewing a change validates the new revision for the change's task. Validating for optimization needs an optimization request (decisions, objective and starts), and a change carries none, so this version refuses rather than report a revision ready for a task it has not checked."
    action: "Commit the change with the task \"simulation\"; then validate the committed revision with the task \"optimization\" and an optimization request."
    gap: {limitation: null, capability: "checking a change for the optimization task when it is committed or previewed"}
    see_also: [unsupported]
    examples:
      - chain: [unsupported, task_unsupported]
        params: {task: optimization}
```

## 5. Work order for the build lane (lane: build; one commit, package MSG)

Steps 1–3 and 7–8 are verbatim edits; a `sonnet-implementer` may take them. Step 4 needs Opus or a careful Sonnet:
it is harness plumbing, not prose. Do not run the full gate (CLAUDE.md, gate by risk). Run the tests in step 10. CI
green is the merge condition.

1. **`src/openflowsheet/messages/catalogue/refusals.yaml`.** Replace the whole entries of these codes with the YAML in
   §3.1–§3.3 and §4, verbatim: `warm_start_unit_unknown`, `nlp_solver_unavailable`, `request_invalid`, the seven
   stubs and `task_unsupported`.
   - `warm_start_source_missing` is unchanged.
   - No `review:` line remains on any of these entries.
2. **`src/openflowsheet/messages/catalogue/scan-allow.yaml`.** Replace the three reason lines given in §3.4.
3. **`benchmarks/t08/support_envelope.yaml`.** Make L-OPT-2's last line as §3.5 gives it. Then run:
   - `python scripts/t08_support_matrix.py --emit`, then `--check` (this rewrites `docs/support-matrix.md`);
   - `python scripts/msg_catalogue.py sync-limitations`, then `sync-limitations --check` (this rewrites
     `limitations.yaml`).
4. **`tests/test_msg_corpus.py`.** Run C12 with the unavailable probe (§4, Amendment 1) in every C12 node: the setup
   and the four-transport node.
   - The mechanism is the engineer's choice, e.g. a per-case patch table that a fixture applies.
   - `_c12` asserts, before acting, that `closure.audited_solver().available is False`. This makes the precondition
     executable.
5. **`tests/fixtures/msg/corpus.yaml`.** Set C12 `gap: {limitation: L-OPT-1, capability: true}`. Regenerate the texts
   with `pytest tests/test_msg_corpus.py --msg-update`. The diff is C12's `gap`, `Why:` and `Do:` lines only.
6. **Regenerate the generated files.**
   - Docs: `python scripts/doc_pages.py`, then `--check` (`docs-site/messages/refusals.md`, `limitations.md`, and
     `docs-site/guide/limitations.md` if it is generated).
   - Schema fixtures: `python scripts/t07_schema_fixtures.py --write`. It rewrites only the fixtures that differ: the
     `message_entry` fixtures that carry the catalogue digest, i.e. `valid/phase_regime_mismatch.json` and
     `invalid/missing_code.json`, as D-92 did.
   - CLI pins: `PYTHONPATH=src:. python tests/test_t07_w5b_cli.py --write-pins`. The diff must be the U05 record's
     stderr `Why:` and `Do:` lines only.
   - Do **not** touch `tests/fixtures/opt/pre_opt_u05.json` or `tests/fixtures/opt/pre_opt_descriptions/`. They are
     historical captures that the reversal tests restore, not re-render.
7. **`tests/test_msg_engine.py`.** Add the test for A5 (§6): two parametrized cases of `render_error`.
8. **`docs/design/MSG-messages.md`.** Two amendments, verbatim:
   - §3.6, the "Size for 0.4" bullet: after "a turbine pressure rise and an unsupported task", insert
     " (C12; since ADR 0071, the default install's missing audited NLP solver — ruling
     `docs/reviews/MSG-catalogue-X02-OPT.md`)".
   - §7, the corpus table's C12 row becomes:
     `| C12 | \`validate --task optimization\` without an audited NLP solver (the probe forced unavailable in the test) | \`nlp_solver_unavailable\` / not_supported; \`gap.limitation\` L-OPT-1 | — (\`optimise\` in the summary; action token \`nlp\`) | all four |`
   - Directly under the table, add: `*C12 amended 2026-11-09 (ADR 0071 R-968; ruling docs/reviews/MSG-catalogue-X02-OPT.md): was \`task_unsupported\`.*`
9. **`docs/OPT_DECISIONS.md`.** Add the next D-number. It records that the ruling was applied, cites this note, and
   gives the catalogue digest change `7bbe3d65…` → `5e5026c5…` and the commit.
10. **Run these tests:**
    - `pytest tests/test_msg_engine.py tests/test_msg_coverage.py tests/test_msg_corpus.py tests/test_msg_explain.py tests/test_t07_w5b_cli.py tests/test_t07_w5e_application_results.py tests/test_t08_w2_unsupported.py tests/test_opt_cli.py tests/test_t07_conformance.py`;
    - `python scripts/msg_catalogue.py check`;
    - `ruff` on the changed test files.

**If a number in §6 does not come out as stated after a verbatim application, stop and report it to the design
lane.** Do not adjust the YAML until the number matches.

## 6. Acceptance: numbered assertions

**How the numbers were made.** A scratch harness, not committed, applied §3–§4's blocks and the new L-OPT-2 text in
memory to `main` at `c1ced8a7` and built a `Catalogue` from them:

- **Lint.** `lint(…, released)` passed.
- **Review count.** `review_count` went from 138 to 129.
- **Digest.** `Catalogue.sha256()` went from `7bbe3d657199…77f36` to the value in A2. The "before" value equals the
  committed fixture, which is the control.
- **Rendering.** Every changed entry's examples rendered with `strict=True` on the `python` and `cli` surfaces, and so
  did the six real refusal documents quoted in A4–A5.

Every expectation below is executable through an existing repository command or a test that step 7 adds. All of
them are exact: there are no floats here, so there is no tolerance to argue.

| # | Assertion | Expected | Checked by |
| --- | --- | --- | --- |
| A1 | Catalogue check | `MSG check PASS`: 379 entries, 83 complete, `review: true` on 129 | `python scripts/msg_catalogue.py check` |
| A2 | Catalogue digest | `5e5026c52a16bb5f9d0f0d481d706bc663f704e69e89f38889a810b47fb84616`. The digest is over parsed values, so YAML formatting is free and scalar text is not. | the regenerated `message_entry` fixtures (`tests/test_t07_w5e_application_results.py`) |
| A3 | G4 | 0 lint problems; every changed complete entry's examples render on every reachable variant | `tests/test_msg_engine.py` |
| A4 | C12 | `nlp_solver_unavailable` / `not_supported`, chain `[unsupported, nlp_solver_unavailable]`, `gap.limitation == "L-OPT-1"`, capability non-empty, `optimise` in the summary, `nlp` in the action. The documents are equal across the four transports. The node runs, and does not skip, whatever the machine's own probe says. | `tests/test_msg_corpus.py` |
| A5 | `request_invalid` names the member inside the request | `invalid_request` with `request_invalid(/objective/kind): …` and `detail.pointer` `/request/objective/kind` gives the summary `The optimisation request is invalid at /objective/kind.`; with `request_invalid(): …` and `detail.pointer` `/body/request` it gives `The optimisation request is invalid.` | the new test in `tests/test_msg_engine.py` (step 7) |
| A6 | CLI pins | Only the U05 record's stderr `Why:`/`Do:` lines differ from `main`; `PINS_T07_SHA256` still holds after the reversals | `tests/test_t07_w5b_cli.py` |
| A7 | Generated files | `doc_pages.py --check`, `t08_support_matrix.py --check` and `sync-limitations --check` are all clean | those commands |
| A8 | G2 | 0 codes without an entry or an allow-list reason; the scan-allow keys are unchanged | `msg_catalogue.py check` / `tests/test_msg_coverage.py` |
| A9 | I1 | Every machine message is unchanged; U05 and `test_opt_cli` pass without edits | `tests/test_t08_w2_unsupported.py`, `tests/test_opt_cli.py` |

**Why A5 cannot pass by accident.** The two candidate pointers differ: the arg is `/objective/kind`, the envelope
pointer is `/request/objective/kind`. If the arg rename were reverted, the `detail` member would win, the summary
would read `…/request/objective/kind.`, and A5 would fail.

**Why A4 cannot pass by accident.** If `gap.limitation` were left null, or C12 were re-pointed elsewhere, A4 would
fail, because it names L-OPT-1 and the exact chain.

## 7. What this ruling does not establish

- **It checks prose and kinds, nothing else.** It does not validate the physics or the numerics behind the OPT
  readiness checks (whether probing the ends of the bounds is the right continuity test, the margin definitions).
  Their summaries describe the emission sites as they stand at `c1ced8a7`.
- **It does not complete the seven readiness stubs.** Their `explain` output still ends with the kind's default
  action.
- **C12 stays a regression fixture.** Its code, kind, chain and gap come from an independent source (ADR 0071 D8,
  R-968; OPT §4.11). Its text golden is self-generated.
- **The forced probe proves nothing about the real probe.** C12 does not check the real probe on any platform. That
  is U05's and G11's job (`test_t08_w2_unsupported.py`, `test_opt_cli.py`).
- **No identity is touched.** There is no machine message, schema, bundle or replay change, and no F0 effect: the
  catalogue digest is outside every identity (MSG §3.2, I2).
- **It does not cover the codes or labels the brief did not list,** apart from `task_unsupported`, which the C12
  question forced (§4). In particular `warm_start_rejected(…)`, `PHASE_REGIME_CHANGED(…)` and M03's readiness stubs
  are untouched.

## 8. Findings outside the brief, each with a default

**F1. OPT's validation check ids escape G1, and none of them can have a core entry.**

- **The defect.** G1 is normatively "every validation check id that `validation.py` can emit" (MSG §3.2). Its
  collector matches only `"[A-Z]+-\d{2}"` (`msg_catalogue.py:146-149`), so it misses `OPT.REQUEST_SCHEMA` and every
  `f"OPT.{code}"` (`validation.py:403`, `:527`).
- **Why no entry can be added.** A `.` in a core code is reserved for extension namespaces, and the loader refuses it
  (`catalogue.py:306-307`).
- **The consequence.** The CLI prints no explanation line under a failing `OPT.*` check.
- **Status.** This is a gap in what the gate covers, not a wrong message. It needs an MSG design decision, from the
  design lane, not the user.
- **Recommended default, as a separate small MSG follow-up and not part of this work order:**
  - explain `OPT.<CODE>` by the entry `<CODE>`, and `OPT.REQUEST_SCHEMA` by `request_invalid`, in both
    `_check_line` and `_report_chain`;
  - make G1 enumerate `STATIC_CODES` and `request_invalid` as members that must have entries;
  - complete in the same change every readiness stub this makes reachable (MSG review Q2). That includes giving
    `REVISION_UNBOUND` a code-typed arg so that its inner refusal is reached.

**F2. The W5b CLI pin of U05 depends on the install in the same way C12 did.**

- `validate CASE --task optimization` with no `--request` gives `invalid_request` where the audited solver is present.
- It is latent: the audited environment runs only `-m nlp`.
- **Default:** no action now. If the default suite is ever run in the audited environment, give U05's capture the same
  unavailable double.

**F3. The brief's premise that "all [entries] are flagged `review: true`" is inaccurate for X02** (§2). This is
recorded and needs no action.

## 9. Open questions

- **Needs Frank:** no. Every choice above is a prose, kind or test-harness ruling inside the design lane's remit, and
  each one can be undone by a revert.
- **Open for the design lane:** only F1, which has its default above and is not blocking.
