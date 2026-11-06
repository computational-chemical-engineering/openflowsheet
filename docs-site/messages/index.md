# Messages

Every error, refusal, run outcome, validation check, status and limitation in OpenFlowsheet carries a
**code**, and every code has an explanation written for a person who has just made the mistake. The
explanation is rendered when you read it, from the message catalogue; the machine message beside it
never changes, so a program that matched the old text still matches.

The pages of this section list every code, one section per code:

| Page | Codes |
| --- | --- |
| [API errors](api-errors.md) | the error codes every transport returns (`ApiError.code`) |
| [Refusals](refusals.md) | the specific reasons a request, a revision, a solve or a project is refused |
| [Run outcomes](outcomes.md) | how a solve ended (`RunResult.outcome`) |
| [Validation checks](checks.md) | the checks of a validation report |
| [Statuses](statuses.md) | validation statuses and certificate words |
| [Limitations](limitations.md) | what this version does not do, one section per support-matrix row |
| [Notices](notices.md) | messages that are not failures |
| [Jobs](jobs.md) | why a job ended the way it did |

Each explanation's `docs` link points at its code's section here.

## Reading an explanation

Python's `str()` of an error, and the command line's stderr, show the explanation in layers: what
happened and where, why (with the numbers), what to do, then the kind, the code and the machine
details.

```text
<summary>
  Cause:   <the inner reason, when the summary is the outer one>
  Why:     <the rule, with the numbers>
  Do:      <what to change>
  Hint:    <the binder's hint, verbatim>
  Kind:    <one of the five kinds below>
  Code:    <code>[, in <outer codes>] (openflowsheet explain <code>)
  Docs:    <this site's section for the code>
  Details: <the machine message, unchanged>
```

A line is left out when it has nothing to say. For example, the example of
[`phase_regime_mismatch`](refusals.md#phase_regime_mismatch), a turbine outlet declared wet that
comes out vapour:

```text
The solve stopped before its first iteration: unit 'T' could not compute its outlets from the starting values.
  Cause:   Stream 'S4' is not in its declared phase: it is declared wet (vapour + liquid), but at these conditions it is vapour.
  Why:     At 10000 Pa the enthalpy of 'S4' is 47330 J/mol, above the saturated-vapour value 46570 J/mol, so the stream is vapour, not wet (vapour + liquid).
  Do:      Declare 'S4' as vapour. If you expected wet (vapour + liquid), check the specifications that set the conditions upstream of 'S4'.
  Kind:    Input problem: something in the flowsheet or the request needs to change.
  Code:    phase_regime_mismatch, in INITIALIZATION_FAILED → initializer_failed (openflowsheet explain phase_regime_mismatch)
```

## The five kinds

| Kind | Meaning |
| --- | --- |
| `input` | Input problem: something in the flowsheet or the request needs to change. |
| `not_supported` | Not supported in this version: a limitation of OpenFlowsheet, not an error in your flowsheet. The explanation names the limitation (`gap`). |
| `numerical` | Numerical failure: the solver did not find the solution; your flowsheet may be correct. |
| `bug` | Internal error in OpenFlowsheet: please report it. |
| `notice` | Notice: not a failure. |

## Explanations as data

Programs and agents read the same explanation as a document
(`application-results.schema.json#/$defs/explanation`): `code`, `family`, `kind`, `complete`,
`summary`, `cause`, `where`, `why`, `action`, `hint`, `elements` (the flowsheet ids involved), `numbers`
(each with its label, SI value, unit and quantity kind), `gap` (for a not-supported code: the
limitation and the missing capability), `chain` (the codes, outer to inner) and `docs`.

- A refusal on any transport carries it as `detail.explanation` of the `ApiError` document.
- A solve that did not converge carries it as `RunResult.failure.explanation`; `failure` also holds
  the outcome, the stored failure message, the implicated elements, the suggested actions and the
  failure bundle's artifact id.

A section that says *no plain-language explanation is written yet* is a code whose entry is still the
technical summary; the code, the kind and the machine message are complete.

## Asking for a code: `explain`

`explain` returns a code's catalogue entry: its title, kind, the templates of its summary, why and
action (each parameter shown as `<name>`), the parameters, the gap, related codes, rendered examples
and its docs link. It reads no project.

- Command line, no project needed: `openflowsheet explain phase_regime_mismatch` prints the entry as
  text, `--json` as the document. An unknown code exits 6 (`not_found`) and suggests close codes.
- Python: `LocalApplication.explain(code)` returns a `MessageEntry`.
- HTTP: `GET /v1/explain/{code}`. MCP: the `explain` tool.
- Every transport refuses an unknown code `not_found`, with `detail.code` and
  `detail.suggestions` (up to five codes within three edits, case-insensitive).

## The beginner-mistake corpus

The explanations are tested against a corpus of beginner mistakes, `tests/fixtures/msg/corpus.yaml`,
each built from the README's Rankine change set through the public API. A case records:

- `id` and the `mistake`, in a sentence;
- the emitted `code`, `kind` and `chain`, exactly;
- the `elements` ids that must appear in `explanation.elements` and in the summary (line 1 and
  its cause), and `in_summary` texts the summary must contain;
- the `numbers` names, with values where an independent expectation exists;
- an `action_token` the action must contain, and the `gap` of a `not_supported` code;
- the complete rendered text per surface, `text`, as an exact golden (regenerated only by
  `pytest tests/test_msg_corpus.py --msg-update` and reviewed in the diff);
- the `surfaces` it runs on; a case on all four must give one document on all of them;
- `pending` items: what the design expects and the software does not emit yet, each a strict
  expected failure that turns the test red the day it holds.

A case's Python setup function lives in `tests/test_msg_corpus.py`, keyed by its `id`. A case records
the code the software actually emits; a code that is too unspecific is reported, never invented.
