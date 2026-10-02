# `evidence/`

Acceptance evidence for each work package: the commands actually run, the checks they produced,
and the artifacts they reference (implementation plan §7; blueprint §16). Evidence is what lets
a later session resume without re-deriving trust, and what a gate verdict points at.

## Layout

```
evidence/<package>/<code-commit-hash>/manifest.json
evidence/<package>/<code-commit-hash>/artifacts/...      (gitignored)
```

- `<package>` is a work-package ID from implementation plan §4 (`P00`, `K03`, `T06`, ...).
- `<code-commit-hash>` is the full 40-character hash of **the code commit the evidence was
  produced from** — not the commit that carries the manifest. A manifest cannot contain its own
  commit hash, so the sequence is: commit the code (commit A), run the acceptance commands
  against A, write `evidence/<package>/<A>/manifest.json`, and commit the manifest in the
  *following* commit (commit B, message `<ID>: add evidence manifest`). If a fix is needed, the
  fix is a new code commit and gets its own evidence directory.
- `artifacts/` holds bulky outputs — traces, dumps, generated ensembles, binary inventories.
  It is gitignored (`evidence/**/artifacts/`). Artifacts are referenced from the manifest by
  path, SHA-256, and description, never pasted into commit prose.

`tests/test_evidence_manifests.py` enforces this layout: it validates every manifest against
`schemas/evidence-manifest.schema.json`, checks that the directory names match the recorded
`work_package` and `commit`, and checks with `git cat-file -e` that the recorded commit object
actually exists in the repository.

## Manifest fields

Per implementation plan §7 and `schemas/evidence-manifest.schema.json`:

| Field | Content |
| --- | --- |
| `work_package` | Package ID; must equal the parent directory name |
| `commit` | 40-hex hash of the code commit the evidence was produced from |
| `requirements` | Requirement IDs (`D01`, `A08`, ...) this evidence supplies; empty only if the package maps to no requirement, which must then be stated in `limitations` |
| `status` | See vocabulary below |
| `inputs` | `case_id`, `case_hash`, `environment_lock_hash` |
| `commands` | Each `{cmd, cwd, exit_code}`, optionally `stdout_sha256` — the commands actually run |
| `checks` | Each `{id, description, result}` with optional `value`, `expected`, `tolerance`; `result` is `pass`, `fail`, `unsupported`, or `not_applicable` |
| `artifacts` | Each `{path, sha256, description}` |
| `limitations` | What this evidence does *not* establish |
| `review` | `{numerical, process_model}` |

## Status vocabulary

`planned | implemented | tested | reviewed | released | BLOCKED`

- `planned` — scoped, not built.
- `implemented` — code exists; acceptance checks not yet run or not yet passing.
- `tested` — the recorded acceptance checks were run against the recorded commit and passed.
- `reviewed` — a second party reviewed it. **Never set by the package's own lead lane**
  (`CLAUDE.md`; plan §1.3, "Cross-review, never self-review"). The design lane (`reviewer`) reviews build-lane work
  touching residuals, derivatives, phase logic, scaling, certificates, or replay identity; the
  build lane reviews design-lane work for coverage, packaging, and documentation.
- `released` — part of a tagged release whose gate verdicts are recorded.
- `BLOCKED` — a prerequisite is genuinely unavailable. Never counted as a pass, never merged as
  done, and never removed from a gate's denominator (plan §5.1, §1.1).

Only `tested` (or better) may be merged to `main` as complete (`CLAUDE.md`, "Branch and merge
discipline").

## Review fields

`review.numerical` and `review.process_model` are each either the literal string `pending` or a
reviewer identity and date (for example `Frank Peters, 2026-09-20`). They are never set by the
package's own lead model, and an agent may not claim human numerical or process-modeling
sign-off, which is recorded separately (plan §7).

## Placeholders

Angle-bracket text such as `<actual commit hash>` in the plan's field list is a schema example.
It is never a valid evidence value; the manifest test rejects any string containing an
angle-bracket placeholder anywhere in the document (`CLAUDE.md`, "Scientific conduct").

Manifests distinguish `implemented`, `tested`, `reviewed`, and `released`, and they distinguish
numerical verification from empirical validation from optimality evidence. A manifest describes
what was actually run; it never asserts a check that was not executed.
