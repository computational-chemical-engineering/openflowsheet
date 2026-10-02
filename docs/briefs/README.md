# Delegation briefs

The briefs that produced the authority documents, harnesses and verdicts of P01, P02 and P03,
kept as worked examples. **They are history, not authority.** Where a brief and a committed
document disagree, the document is right: several of these briefs contain statements that
measurement later corrected, and those corrections are recorded in the documents and in
`docs/progress.md`, not here.

| File | Model | Produced |
| --- | --- | --- |
| `P01-oracle-implementation.md` | Opus | The SYN-001 oracle, registry, schemas and tests |
| `P02-specification-design.md` | Fable | `docs/derivations/P02-composition-spec.md` and its reference values |
| `P02-pyomo-harness.md` | Opus | `spikes/p02/pyomo/` and its result set |
| `P02-implementation-review.md` | Fable | The review that found the judge's coverage defect |
| `P03-backend-verdict.md` | Fable | ADR 0003 and ADR 0006 — the backend and distribution verdicts |

Three things made them work, and are worth copying rather than the prose around them.

1. **Paste the numbers in.** A brief that points at a file pays the expensive model to read the
   repository. Every constant, closed form and measured value the decision turns on is in the text.
2. **Separate what is decided from what is open.** The settled section stops an agent relitigating
   the plan; the open section is the actual question. Both are needed, and the second is short.
3. **Say what was already tried and rejected, with the evidence.** This is the section that stops a
   design pass handing back a dead end someone already walked down, and it is the one most often
   left out.

The P03 brief adds a fourth, specific to a verdict rather than a design: **say where the evidence
is not comparable**. Its §4.6 lists the four ways the two backend routes are not measuring the
same thing, because a verdict that compares them as though they were is wrong even when it picks
the right winner.

The review brief adds a fifth: **name where you are least sure**. Three of its five listed doubts
turned into findings; the must-fix came from the reviewer looking where it was told the author was
uncertain.
