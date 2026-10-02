"""T07's part of the cross-platform identity (§15 W8, G1), included by `k05_structural_identity.py`.

Design note `docs/design/T07-jobs-and-bindings.md` §15 W8 and §16 G1, with ruling rounds 2 and 3
and `docs/T07_DECISIONS.md` W3-Q3. What the application contract adds to R0, through the contract
itself — `commit_change`, `validate` and `submit_job` on a `LocalApplication` with the inline
executor (§9.1):

- `runs` — per revision of `CASES`, solved with `policy_id = "default"` (the route's registered
  policy, ruling round 1 R2.3):
  - `run_result` — `RunResult`'s `outcome`, `verification_status`, `structural_sha256`,
    `policy_sha256`, `check_policy_sha256`, `revision_content_sha256`, `solve_path` and
    `job_status`;
  - `events` — the job's events as `[sequence, kind, ends_job, progress.completed,
    progress.total, progress.stage, output.kind, output.name]` (`null` where the event has no
    such member);
  - `validation` — F5 (§12.4): the stored revision's validation report for `simulation`, its
    `status`, `checks`, `structural_counts` and their absent reason; `provenance` is excluded
    (ruling round 1 R3: production metadata, and it carries a clock reading);
  - `r0` — `r0_projection` of the bundle's artifacts **as written** (W3-Q3), which carries the
    execution plan, the solve path, the solution state's ids (ruling round 2 F1.3) and the
    failure bundle's R0 (ruling round 3 Q1), with the manifest's `artifact_r0_sha256`; the script
    asserts that digest recomputes from the bundle.
- `q29` — G10's vector set (R-088 Q29, §12.5): every numeric leaf of `Q29_REVISIONS` × `VECTORS`,
  per leaf `[validate's status, its non-PASS checks as [id, result, message], the legacy binder's
  refusal as [kind, detail, implicated], the revision binder's, commit_change's as [status, code,
  pointer]]`. A binder that binds is `null`; `commit_change` is tried with the non-canonical
  values only (a non-number is canonical JSON and commits), as the whole mutated document, so its
  pointer names the leaf. Leaves are grouped by that entry with their pointer written `<p>` and
  the commit's `<edit-p>` (`_template`): `[[entry, [pointers]], ...]`, 1.5 MB → a few kB.
- `adr0002_a1` — ADR 0002 Amendment 1's 22 registered integers
  (`docs/derivations/scripts/adr0002_a1_reference.json`): per row `[id, n, commit_change's
  status, its error code, its pointer]` for a `set` of the integer.

`CASES` cover both routes (`legacy_eo`: SYN-001-A02-360) and the registered initializer's failure
bundle (SYN-001-UL-C3X, ruling round 3 Q1); SYN-001-nominal, C2 (SYN-001-UL-C2), NET-02 and
STA-04 are §15 W8's own.

Floats-free: every member is a string, an integer, a boolean or null. Digests are of declared
inputs (the revision's canonical bytes, the policies), of R0 structure (`structural_sha256`,
`artifact_r0_sha256`: K05 carries both) — never of a computed state. Nothing volatile enters: no
job, run or artifact id, no timestamp, host, elapsed time or output digest (the run manifest's
bytes carry the clock). Every call builds a fresh project, so two calls are two sets of solves.
"""

from __future__ import annotations

import copy
import json
import math
import sys
import tempfile
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

#: §15 W8's revisions, then one `legacy_eo` run with a certificate and one run ending at the
#: registered initializer's refusal with a failure bundle (ruling round 3 Q1).
CASES = (
    "SYN-001-nominal",
    "SYN-001-UL-C2",
    "SYN-001-T06-NET02",
    "SYN-001-T06-STA04",
    "SYN-001-A02-360",
    "SYN-001-UL-C3X",
)
#: The `RunResult` members the key carries (§15 W8); ids, outputs and the error are not R0.
RUN_RESULT_MEMBERS = (
    "outcome",
    "verification_status",
    "structural_sha256",
    "policy_sha256",
    "check_policy_sha256",
    "revision_content_sha256",
    "solve_path",
    "job_status",
)
#: G10's five registered revisions (`tests/test_t07_w2d_noncanonical.py`, `REVISIONS`).
Q29_REVISIONS = (
    "benchmarks/syn001/cases/SYN-001-nominal.yaml",
    "benchmarks/syn001/cases/SYN-001-A02-360-vapor-guess.yaml",
    "benchmarks/t06/cases/SYN-001-T06-STA03-degC.yaml",
    "benchmarks/t06/cases/SYN-001-T06-NET02.yaml",
    "benchmarks/t05/cases/SYN-001-UL-C1.yaml",
)
#: G10's vector set: label -> (value, canonical JSON?). The numbers ADR 0002 D3.3/D3.4 give no
#: canonical form, the non-numbers, and ruling round 4's lone surrogates (W5a-Q1).
VECTORS: dict[str, tuple[object, bool]] = {
    "NaN": (math.nan, False),
    "+inf": (math.inf, False),
    "-inf": (-math.inf, False),
    "2^53+1": (2**53 + 1, False),
    "-(2^53+1)": (-(2**53 + 1), False),
    '"x"': ("x", True),
    "true": (True, True),
    "null": (None, True),
    '"\\ud800"': ("\ud800", False),
    '"a\\udfffb"': ("a\udfffb", False),
    '"\\ud83d\\ude00"': ("\ud83d" + "\ude00", False),
}
A1_REFERENCE = ROOT / "docs" / "derivations" / "scripts" / "adr0002_a1_reference.json"


# -- the contract's runs ----------------------------------------------------------------------


def _commit(application: Any, document: Mapping[str, Any], key: str) -> str:
    """`document` as the new head revision (one `set` per top-level key); its id."""
    from openflowsheet.application.types import Change, Edit

    with application.store.reading() as connection:
        head = application.store.head(connection)
    edits = tuple(Edit("set", (name,), value) for name, value in document.items())
    result = application.commit_change(Change(edits=edits), head, key)
    assert result.status == "committed" and result.revision_id is not None, result
    return str(result.revision_id)


def _event(event: Any) -> list[Any]:
    progress, output = event.progress, event.output
    return [
        event.sequence,
        event.kind,
        event.ends_job,
        None if progress is None else progress.completed,
        None if progress is None else progress.total,
        None if progress is None else progress.stage,
        None if output is None else output.kind,
        None if output is None else output.name,
    ]


def _validation(report: Any) -> dict[str, Any]:
    document = report.as_document()
    return {
        name: document[name]
        for name in ("status", "checks", "structural_counts", "structural_counts_absent_reason")
        if name in document
    }


def _r0(application: Any, job: Any) -> dict[str, Any]:
    """The bundle's R0 from its files (W3-Q3), and the manifest's digest of it."""
    from openflowsheet.run.bundle import read_artifact, read_manifest
    from openflowsheet.run.identity import r0_projection, r0_sha256

    (bundle,) = [output for output in job.outputs if output.kind == "replay_bundle"]
    row = application.store.artifact(bundle.artifact_id)
    assert row is not None, bundle
    directory = application.files_root / row.relpath
    manifest, _ = read_manifest(directory)
    projection = r0_projection(
        {name: read_artifact(directory, name) for name in manifest.artifacts}
    )
    if r0_sha256(projection) != manifest.artifact_r0_sha256:
        raise AssertionError(f"{job.job_id}: artifact_r0_sha256 does not recompute from the bundle")
    return {"artifact_r0_sha256": manifest.artifact_r0_sha256, **projection}


def runs(application: Any) -> dict[str, Any]:
    """`CASES` through `application`'s contract: commit, validate, submit a solve, read back.
    Executor-neutral, so a test can compare the inline record with the process executor's."""
    from t07_corpus import CORPUS

    from openflowsheet.application.types import JobRequest, SolveBody

    out = {}
    for case in CASES:
        revision_id = _commit(application, CORPUS[case](), f"t07-identity-commit:{case}")
        report = application.validate(revision_id, "simulation")
        request = JobRequest(
            "solve", f"t07-identity:{case}", SolveBody(revision_id=revision_id, policy_id="default")
        )
        job = application.submit_job(request).job
        while job.ending is None:  # inline: already ended; process: wait for the worker
            application.wait_job(job.job_id, after_sequence=job.event_count - 1, timeout_s=math.inf)
            job = application.get_job(job.job_id)
        result = application.get_job_result(job.job_id).run_result
        assert result is not None, job
        snapshot = application.store.job_snapshot(job.job_id)
        assert snapshot is not None, job
        out[case] = {
            "run_result": {name: getattr(result, name) for name in RUN_RESULT_MEMBERS},
            "events": [_event(event) for event in snapshot[1]],
            "validation": _validation(report),
            "r0": _r0(application, job),
        }
    return out


# -- Q29 (G10) --------------------------------------------------------------------------------


def _pointer(path: tuple[str | int, ...]) -> str:
    return "".join("/" + str(token).replace("~", "~0").replace("/", "~1") for token in path)


def _numeric_leaves(node: object, path: tuple[str | int, ...] = ()) -> Iterator[tuple[Any, ...]]:
    if isinstance(node, bool):
        return
    if isinstance(node, int | float):
        yield path
    elif isinstance(node, Mapping):
        for key, value in node.items():
            yield from _numeric_leaves(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _numeric_leaves(value, (*path, index))


def _with(document: Any, path: tuple[Any, ...], value: object) -> Any:
    mutated = copy.deepcopy(document)
    node = mutated
    for token in path[:-1]:
        node = node[token]
    node[path[-1]] = value
    return mutated


def _refusal(binding: Any) -> list[Any] | None:
    from openflowsheet.application.binding import Unbound

    if isinstance(binding, Unbound):
        return [binding.kind, binding.detail, list(binding.implicated)]
    return None


def _commit_refusal(application: Any, document: Mapping[str, Any], key: str) -> list[Any]:
    from openflowsheet.application.types import Change, Edit

    edits = tuple(Edit("set", (name,), value) for name, value in document.items())
    result = application.commit_change(Change(edits=edits), None, key)
    error = result.error
    return [
        result.status,
        None if error is None else error.code,
        None if error is None else dict(error.detail or {}).get("pointer"),
    ]


def _template(node: Any, pointer: str, edit_pointer: str) -> Any:
    """`node` with the leaf's pointer written `<p>` and its `commit_change` pointer `<edit-p>`:
    as a whole string, or as `(<pointer>)` inside a typed code. Invertible given the pointers,
    so grouping leaves by template loses nothing."""
    if isinstance(node, str):
        if node == pointer:
            return "<p>"
        if node == edit_pointer:
            return "<edit-p>"
        return node.replace(f"({pointer})", "(<p>)")
    if isinstance(node, list):
        return [_template(item, pointer, edit_pointer) for item in node]
    return node


def _q29(application: Any) -> dict[str, Any]:
    """Per revision and vector, `[[entry, [leaf pointers]], ...]`: the leaves grouped by their
    entry's template, in first-occurrence order (a leaf whose codes differ opens a group)."""
    import yaml

    from openflowsheet.application.binding import bind_revision_or_reason
    from openflowsheet.application.revision_binding import bind_revision_flowsheet
    from openflowsheet.application.validation import validate

    out: dict[str, Any] = {}
    for name in Q29_REVISIONS:
        document = yaml.safe_load((ROOT / name).read_text("utf-8"))
        keys = list(document)
        stem = Path(name).stem
        per_vector: dict[str, Any] = {}
        for label, (value, canonical) in VECTORS.items():
            groups: dict[str, list[Any]] = {}
            for index, path in enumerate(_numeric_leaves(document)):
                pointer = _pointer(path)
                mutated = _with(document, path, value)
                report = validate(copy.deepcopy(mutated))
                entry = [
                    report.status,
                    [
                        [check.id, check.result, check.message]
                        for check in report.checks
                        if check.result != "PASS"
                    ],
                    _refusal(bind_revision_or_reason(copy.deepcopy(mutated))),
                    _refusal(bind_revision_flowsheet(copy.deepcopy(mutated))),
                    None
                    if canonical
                    else _commit_refusal(
                        application, mutated, f"t07-identity-q29:{stem}:{label}:{index}"
                    ),
                ]
                edit_pointer = f"/edits/{keys.index(path[0])}/value{_pointer(path[1:])}"
                template = _template(entry, pointer, edit_pointer)
                group = groups.setdefault(json.dumps(template), [template, []])
                group[1].append(pointer)
            per_vector[label] = list(groups.values())
        out[stem] = per_vector
    return out


# -- ADR 0002 Amendment 1 ---------------------------------------------------------------------


def _adr0002_a1(application: Any) -> list[list[Any]]:
    from openflowsheet.application.types import Change, Edit

    rows = json.loads(A1_REFERENCE.read_text("utf-8"))["integers"]
    out = []
    for row in rows:
        with application.store.reading() as connection:
            head = application.store.head(connection)
        result = application.commit_change(
            Change(edits=(Edit("set", ("settings", "x"), int(row["n"])),)),
            head,
            f"t07-identity-a1:{row['id']}",
        )
        error = result.error
        out.append(
            [
                row["id"],
                row["n"],
                result.status,
                None if error is None else error.code,
                None if error is None else dict(error.detail or {}).get("pointer"),
            ]
        )
    return out


def identity() -> dict[str, Any]:
    from openflowsheet.application.local import LocalApplication
    from openflowsheet.application.types import Change, Edit

    with tempfile.TemporaryDirectory() as scratch:
        solving = LocalApplication.create(Path(scratch) / "runs", project_id="t07-identity")
        try:
            recorded = runs(solving)
        finally:
            solving.close()
        refusing = LocalApplication.create(Path(scratch) / "refusals", project_id="t07-refusals")
        try:
            q29 = _q29(refusing)
            seed = Change(edits=(Edit("set", ("settings",), {"mode": "steady"}),))
            assert refusing.commit_change(seed, None, "t07-identity-seed").status == "committed"
            a1 = _adr0002_a1(refusing)
        finally:
            refusing.close()
    return {"runs": recorded, "q29": q29, "adr0002_a1": a1}
