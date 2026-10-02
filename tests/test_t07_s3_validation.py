"""T07 S3: out-of-domain and schema-invalid revisions are typed validation results.

Design note `docs/design/T07-jobs-and-bindings.md`, ruling round 5 S3 (tests S3-1…S3-7) and §12.4
as amended; review finding S3 (`docs/reviews/T07-review.md`). A value a model refuses at
construction reaches `validate`, `preview_change` and `commit_change` as a report, never as an
exception:
- a refused **start** (`role: free`) is the legacy binder's `incomplete`, so `DRAFT` (S3-3);
- a document the frozen revision schema refuses ends at `SCHEMA-01` (S3-5);
- the reviewer's 13,321 single-node mutations raise nothing untyped (S3-6, a sample here; the
  whole population is the manifest's evidence);
- no registered report moves (S3-7).
S3-1, S3-2 and S3-4 — a refused **fixed** value — are the kind-choice tests below (R5-O1).
"""

from __future__ import annotations

import copy
import glob
import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_yaml
from t07_corpus import CORPUS
from t07_jobs_support import commit
from t08_d1_substitution import d1_reversed

from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.types import Change, Edit, schema_errors
from openflowsheet.application.validation import validate
from openflowsheet.canonical import canonical_json

STRUCTURAL = ("STR-01", "STR-02", "STR-03", "STR-04", "STR-05")
#: SHA-256 of `{document: [status, checks]}` over the 94 registered revision documents, as
#: `json.dumps(sort_keys=True)`, measured at `3f9f6f8` (before S3): S3-7's expectation, checked
#: with T08 D1's substitution reversed (`t08_d1_substitution`); `..._D1` is the reports as written.
REGISTERED_REPORTS_SHA256 = "eedea8522833fc029c312e2c32607b4eb4786482c9c53c4bccdcee191ab7486b"
#: Since D1's STR-05 extension (with STR-03's substitution alone it was `0411fe71…`).
REGISTERED_REPORTS_SHA256_D1 = "b2c77ff6c641383868ccab9093bbca727f8f80962675f232a6be944a0afa5b65"
#: The reviewer's population (review S3, `validate_fuzz.py`): five revisions, every node, seven
#: replacement values.
FUZZ_REVISIONS = (
    "benchmarks/syn001/cases/SYN-001-nominal.yaml",
    "benchmarks/syn001/cases/SYN-001-A02-360-vapor-guess.yaml",
    "benchmarks/t06/cases/SYN-001-T06-STA03-degC.yaml",
    "benchmarks/t06/cases/SYN-001-T06-NET02.yaml",
    "benchmarks/t05/cases/SYN-001-UL-C1.yaml",
)
REPLACEMENTS: tuple[Any, ...] = ("x", 7, None, [], {}, ["x"], {"x": 1})


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "project", project_id="s3")
    yield application
    application.close()


def _with_specification(document: dict[str, Any], spec_id: str, value: float) -> dict[str, Any]:
    out = copy.deepcopy(document)
    (entry,) = [entry for entry in out["specifications"] if entry["id"] == spec_id]
    entry["value"] = value
    return out


def _change(document: dict[str, Any]) -> Change:
    return Change(edits=tuple(Edit("set", (key,), value) for key, value in document.items()))


def _checks(report: Any) -> dict[str, Any]:
    return {check.id: check for check in report.checks}


def _typed(report: Any) -> None:
    document = report.as_document()
    assert schema_errors("validation-report.schema.json", document) == []
    canonical_json(document)


# -- S3-3: a refused start is DRAFT ---------------------------------------------------------------


def test_s3_3_a_start_the_model_refuses_is_draft() -> None:
    document = _with_specification(
        CORPUS["SYN-001-A02-360-vapor-guess"](), "GUESS-heater-outlet-T", 7.0
    )
    report = validate(document)
    _typed(report)
    assert report.status == "DRAFT"
    checks = _checks(report)
    assert "CAP-01" not in checks
    for check_id in STRUCTURAL:
        assert checks[check_id].result == "NOT_RUN"
        assert checks[check_id].message.startswith(
            "not run: the revision is incomplete: "
            "start_outside_model_domain(GUESS-heater-outlet-T): U-HEAT: outlet temperature 7.0 K"
        )
        assert checks[check_id].implicated_objects == ("GUESS-heater-outlet-T",)
    assert report.structural_counts is None


# -- S3-5: the frozen revision schema, applied ----------------------------------------------------


def test_s3_5_a_schema_invalid_document_fails_at_schema_01(app: LocalApplication) -> None:
    nominal = CORPUS["SYN-001-nominal"]()
    malformed = copy.deepcopy(nominal)
    malformed["connections"][0]["to"]["instance"] = ["x"]
    report = validate(malformed)
    _typed(report)
    assert report.status == "INVALID"
    (check,) = report.checks
    assert (check.id, check.stage, check.result) == ("SCHEMA-01", "schema", "FAIL")
    assert check.message.startswith("schema_invalid(/connections/0/to/instance): ")
    assert check.implicated_objects == ("/connections/0/to/instance",)
    assert report.structural_counts is None
    assert report.structural_counts_absent_reason == "the revision is not well formed"

    # The review's `commit_malformed.py`: one edit on a committed head, typed through both.
    head = commit(app, nominal)
    edit = Change(edits=(Edit("set", ("connections", 0, "to", "instance"), ["x"]),))
    preview = app.preview_change(edit, head)
    assert preview.status == "previewed"
    assert preview.validation is not None and preview.validation.checks == report.checks
    committed = app.commit_change(edit, head, "s3-5")
    assert committed.status == "committed"  # D16: an INVALID revision is committed with it
    assert committed.validation is not None and committed.validation.status == "INVALID"


def test_s3_5_a_root_error_implicates_no_object() -> None:
    """The root's pointer is empty; the report's own schema requires non-empty ids."""
    report = validate({**CORPUS["SYN-001-nominal"](), "status": "READY_FOR_SIMULATION"})
    _typed(report)
    (check,) = report.checks
    assert check.message.startswith("schema_invalid(): ")
    assert check.implicated_objects == ()


def test_s3_5_a_valid_document_keeps_the_pass_message() -> None:
    (schema,) = [c for c in validate(CORPUS["SYN-001-nominal"]()).checks if c.id == "SCHEMA-01"]
    assert (schema.result, schema.message) == ("PASS", "every required key present")


# -- S3-6: no untyped exception on the reviewer's population (a sample) --------------------------


def _nodes(node: Any, path: tuple[Any, ...] = ()) -> Iterator[tuple[Any, ...]]:
    yield path
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _nodes(value, (*path, key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _nodes(value, (*path, index))


def _mutated(document: Any, path: tuple[Any, ...], value: Any) -> Any:
    out = copy.deepcopy(document)
    node = out
    for step in path[:-1]:
        node = node[step]
    node[path[-1]] = value
    return out


@pytest.mark.parametrize("name", FUZZ_REVISIONS)
def test_s3_6_single_node_mutations_are_typed(app: LocalApplication, name: str) -> None:
    """Every node of the revision × the seven values through `validate`; every 37th of them also
    through `preview_change` and `commit_change`. The whole population, all three entry points,
    is measured by the manifest's probe (0 untyped of 13,321)."""
    document = load_yaml(REPO_ROOT / name)
    head = commit(app, document)
    count = 0
    for path in list(_nodes(document))[1:]:
        for value in REPLACEMENTS:
            mutated = _mutated(document, path, value)
            _typed(validate(copy.deepcopy(mutated)))
            count += 1
            if count % 37:
                continue
            try:
                preview = app.preview_change(_change(mutated), head)
                result = app.commit_change(_change(mutated), head, f"s3-6-{count}")
            except ApplicationError:
                continue
            for outcome in (preview, result):
                if outcome.validation is not None:
                    _typed(outcome.validation)
            if result.status == "committed":
                assert result.revision_id is not None
                head = result.revision_id
    assert count > 1000


# -- S3-7: no registered report moves -------------------------------------------------------------


def test_s3_7_no_registered_report_moves() -> None:
    documents: dict[str, Any] = {name: build() for name, build in CORPUS.items()}
    for path in sorted(glob.glob(str(REPO_ROOT / "benchmarks/**/cases/*.yaml"), recursive=True)):
        documents.setdefault(str(Path(path).relative_to(REPO_ROOT)), load_yaml(Path(path)))
    assert len(documents) == 94
    reports, reversed_d1 = {}, {}
    for name, document in documents.items():
        report = validate(copy.deepcopy(document)).as_document()
        assert "CAP-01" not in [check["id"] for check in report["checks"]], name
        reports[name] = [report["status"], report["checks"]]
        reversed_d1[name] = [report["status"], d1_reversed(report["checks"])]
    digest = hashlib.sha256(json.dumps(reversed_d1, sort_keys=True).encode()).hexdigest()
    assert digest == REGISTERED_REPORTS_SHA256
    digest = hashlib.sha256(json.dumps(reports, sort_keys=True).encode()).hexdigest()
    assert digest == REGISTERED_REPORTS_SHA256_D1


# -- S3-1, S3-2, S3-4: a fixed value the model refuses is INVALID, CAP-01 (R5-O1) ---------------
#
# The kind choice of ruling round 5 S3, pending Frank's preference (R5-O1): the default is
# `INVALID`. The alternative, `DRAFT`, is the binders' kind `inadmissible` → `unsupported`, and
# reverting the commit that carries these tests is exactly that change.


def _capability(report: Any, message: str, implicated: tuple[str, ...]) -> None:
    _typed(report)
    assert report.status == "INVALID"
    checks = _checks(report)
    capability = checks["CAP-01"]
    assert (capability.stage, capability.result) == ("capability", "FAIL")
    assert capability.message.startswith(f"value_outside_model_domain: {message}")
    assert capability.implicated_objects == implicated
    reason = f"the structural analysis did not run: {capability.message}"
    for check_id in STRUCTURAL:
        assert checks[check_id].result == "NOT_RUN"
        assert checks[check_id].message == f"not run: {reason}"
    # Blueprint §4.3's stage order: capability, then the structural analysis.
    assert [check.id for check in report.checks][-6:] == ["CAP-01", *STRUCTURAL]
    assert report.structural_counts is None
    assert report.structural_counts_absent_reason == reason


def test_s3_1_a_fixed_pressure_outside_the_flash_domain_is_invalid(
    app: LocalApplication,
) -> None:
    from openflowsheet.application.operations import dispatch

    nominal = CORPUS["SYN-001-nominal"]()
    report = validate(_with_specification(nominal, "SPEC-feed-P", 3e5))
    _capability(report, "U-FLASH: specified pressure 300000.0 Pa", ("flash",))

    head = commit(app, nominal)
    index = [entry["id"] for entry in nominal["specifications"]].index("SPEC-feed-P")
    edit = Change(edits=(Edit("set", ("specifications", index, "value"), 3e5),))
    preview = app.preview_change(edit, head)
    assert preview.validation is not None and preview.validation.checks == report.checks
    committed = app.commit_change(edit, head, "s3-1")
    assert committed.status == "committed"
    assert committed.validation is not None and committed.validation.checks == report.checks

    # Through the transports' dispatcher (the review's `commit_pressure.py`): no internal_error.
    request = {
        "edits": [{"operation": "set", "path": ["specifications", index, "value"], "value": 3e5}],
        "expected_revision": committed.revision_id,
    }
    previewed = dispatch(app, "preview_change", request)
    assert previewed["validation"]["status"] == "INVALID"
    again = dispatch(app, "commit_change", {**request, "idempotency_key": "s3-1-dispatch"})
    assert (again["status"], again["validation"]["status"]) == ("committed", "INVALID")


def test_s3_2_the_revision_binders_refusal_is_inadmissible_too() -> None:
    """SYN-001-T06-NET03 binds on the revision binder only (the legacy one refuses it
    `unsupported`); its second flash's fixed temperature at 7 K is refused by that model."""
    from openflowsheet.application.binding import bind_revision_or_reason
    from openflowsheet.application.revision_binding import bind_revision_flowsheet

    network = CORPUS["SYN-001-T06-NET03"]()
    assert getattr(bind_revision_or_reason(copy.deepcopy(network)), "kind", None) == "unsupported"
    document = _with_specification(network, "SPEC-fl2-T", 7.0)
    refusal = bind_revision_flowsheet(copy.deepcopy(document))
    assert getattr(refusal, "kind", None) == "inadmissible"
    _capability(validate(document), "U-FL2: specified temperature 7.0 K", ("U-FL2",))


def test_s3_4_a_fixed_value_is_attributed_whatever_the_start() -> None:
    """The start is in range and the flash's fixed temperature is not: the rebuild with the
    guessed column at its declared default is refused too, so the fixed value is the finding."""
    guessed = CORPUS["SYN-001-A02-360-vapor-guess"]()
    fixed = _with_specification(guessed, "SPEC-flash-T", 7.0)
    _capability(validate(fixed), "U-FLASH: specified temperature 7.0 K", ("flash",))
    # Both out of range: the rebuild's refusal, the fixed value's, is the one named.
    both = _with_specification(fixed, "GUESS-heater-outlet-T", 7.0)
    _capability(validate(both), "U-FLASH: specified temperature 7.0 K", ("flash",))
