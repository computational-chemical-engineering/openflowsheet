"""T08.A22: typed outcomes for the envelope's unsupported rows that no earlier test demonstrated.

T08 release spec §5.3 asks each `unsupported` row of `benchmarks/t08/support_envelope.yaml` to name
a test node that shows its outcome. These are the rows (or parts of rows) the existing suite did not
cover; each test asserts what the code does today and nothing more.

- **U02** — a revision has no property-method member (`process-revision.schema.json`,
  `additionalProperties: false`), so naming one is `SCHEMA-01` `INVALID`; a model of another
  property package is the revision binder's `model_unsupported(<id>)`.
- **U05** (T08 review 2, Ruling 1) — `validate(task="optimization")` is ADR 0019's `unsupported`,
  detail `task_unsupported(optimization)`, audited, before the revision is read and with no report
  built; `validation.validate` raises the same refusal; `commit_change` and `preview_change` with
  that task refuse the same way, audited, at the top of `_prepare`.
- **U06** — ADR 0008 D1: a time-varying specification is not representable; a profile value or a
  time member is `SCHEMA-01` `INVALID`.
- **U08** (R-110) — branches: a change set naming one is refused by its schema; in-band policy
  administration and MCP over HTTP: no operation or route exists (ADR 0019 D4; MCP is stdio).
- **U13** — ADR 0006 D1: no mode-B artifact (container, installer, wheelhouse) is tracked.
- **U14** — no CRAFTS / OpenIDAES-450 comparison is registered or shipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from t07_corpus import CORPUS

from openflowsheet.application import validation
from openflowsheet.application.binding import Unbound
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import OPERATIONS
from openflowsheet.application.revision_binding import bind_revision_flowsheet
from openflowsheet.application.types import schema_errors
from openflowsheet.application.validation import validate

ROOT = Path(__file__).resolve().parents[1]


def _schema_refusal(document: dict[str, object], member: str) -> None:
    report = validate(document)
    assert report.status == "INVALID"
    (first, *_) = report.checks
    assert (first.id, first.result) == ("SCHEMA-01", "FAIL")
    assert first.message.startswith("schema_invalid(")
    assert repr(member) in first.message


def test_u02_a_property_method_member_is_a_schema_refusal() -> None:
    document = CORPUS["SYN-001-nominal"]()
    document["property_package"] = "peng_robinson"
    _schema_refusal(document, "property_package")


def test_u02_a_model_of_another_property_package_is_model_unsupported() -> None:
    document = CORPUS["SYN-001-nominal"]()
    (heater,) = (i for i in document["instances"] if i["id"] == "heater")
    heater["model"]["id"] = "peng_robinson.tp_heater"
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == (
        "unsupported",
        "model_unsupported(peng_robinson.tp_heater)",
    )


def test_u05_validate_for_optimization_is_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openflowsheet.application.types import Change, Edit

    document = CORPUS["SYN-001-nominal"]()
    with LocalApplication.create(tmp_path / "project", project_id="u05") as app:
        edits = tuple(Edit("set", (key,), value) for key, value in document.items())
        revision_id = app.commit_change(Change(edits=edits), None, "seed").revision_id
        assert revision_id is not None
        assert app.validate(revision_id, "simulation").status == "READY_FOR_SIMULATION"

        def no_report(*_: object, **__: object) -> None:
            raise AssertionError("a validation report was built")

        monkeypatch.setattr(validation, "ValidationReport", no_report)
        with pytest.raises(ApplicationError) as refused:
            app.validate(revision_id, "optimization")
        assert refused.value.error.as_document() == {
            "code": "unsupported",
            "message": "task_unsupported(optimization)",
            "detail": {"pointer": "/task"},
            "retryable": False,
        }
        audited = [row for row in app.store.audit_rows() if row["outcome"] == "refused"]
        assert [(row["operation"], row["code"]) for row in audited] == [("validate", "unsupported")]

        # The module function refuses the same way, before any stage runs.
        with pytest.raises(ApplicationError) as direct:
            validation.validate(document, "optimization")
        assert direct.value.error == refused.value.error


@pytest.mark.parametrize("operation", ["commit_change", "preview_change"])
def test_u05_a_change_for_optimization_is_refused_audited(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    """U05 on the change path: `commit_change` and `preview_change` with `task="optimization"`
    refuse at the top of `_prepare` with `validate`'s audited `unsupported`,
    `task_unsupported(optimization)`, before any document is built, and write no revision."""
    from openflowsheet.application import local
    from openflowsheet.application.types import Change, Edit

    document = CORPUS["SYN-001-nominal"]()
    with LocalApplication.create(tmp_path / "project", project_id="u05c") as app:
        edits = tuple(Edit("set", (key,), value) for key, value in document.items())
        head = app.commit_change(Change(edits=edits), None, "seed").revision_id
        assert head is not None

        def no_build(*_: object, **__: object) -> None:
            raise AssertionError("a document was built")

        monkeypatch.setattr(local, "apply_edits", no_build)
        change = Change(edits=(Edit("set", ("description",), "x"),), task="optimization")
        with pytest.raises(ApplicationError) as refused:
            if operation == "commit_change":
                app.commit_change(change, head, "optimization")
            else:
                app.preview_change(change, head)
        assert refused.value.error.as_document() == {
            "code": "unsupported",
            "message": "task_unsupported(optimization)",
            "detail": {"pointer": "/task"},
            "retryable": False,
        }
        audited = [row for row in app.store.audit_rows() if row["outcome"] == "refused"]
        assert [(row["operation"], row["code"]) for row in audited] == [(operation, "unsupported")]
        assert [summary.revision_id for summary in app.list_revisions().items] == [head]


def test_u06_a_specification_profile_is_a_schema_refusal() -> None:
    document = CORPUS["SYN-001-nominal"]()
    specification = document["specifications"][0]
    specification["value"] = [[0.0, 1.0], [60.0, 2.0]]
    report = validate(document)
    assert report.status == "INVALID"
    assert (report.checks[0].id, report.checks[0].result) == ("SCHEMA-01", "FAIL")


def test_u06_a_time_member_is_a_schema_refusal() -> None:
    document = CORPUS["SYN-001-nominal"]()
    document["specifications"][0]["time"] = {"start": 0.0, "end": 60.0}
    _schema_refusal(document, "time")


def test_u08_a_change_set_naming_a_branch_is_refused_by_its_schema() -> None:
    change = {"edits": [], "expected_revision": None, "idempotency_key": "k", "branch": "b"}
    assert schema_errors("change-set.schema.json", change) != []
    del change["branch"]
    assert schema_errors("change-set.schema.json", change) == []


@pytest.mark.parametrize("name", ["install", "policy", "publish", "set_policy", "register_policy"])
def test_u08_no_operation_administers_policies(name: str) -> None:
    assert name not in OPERATIONS


def test_u08_mcp_is_not_served_over_http() -> None:
    """Every HTTP route is a `/v1/` operation route; no MCP endpoint exists on HTTP (R-110)."""
    routes = [row.http for row in OPERATIONS.values() if row.http is not None]
    assert routes
    assert all(path.startswith("/v1/") for _, path in routes)
    assert not any("mcp" in path.lower() for _, path in routes)


def _tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
    ).stdout
    return listed.splitlines()


def test_u13_no_mode_b_artifact_is_tracked() -> None:
    names = {Path(path).name.lower() for path in _tracked()}
    suffixes = {Path(path).suffix.lower() for path in _tracked()}
    assert not names & {"dockerfile", "containerfile", "docker-compose.yml", "compose.yaml"}
    assert not suffixes & {".whl", ".msi", ".exe", ".dmg", ".pkg", ".deb", ".rpm", ".appimage"}
    assert not any("wheelhouse" in path.lower().split("/") for path in _tracked())


def test_u14_no_external_benchmark_comparison_is_registered() -> None:
    registry = (ROOT / "benchmarks" / "registry.yaml").read_text(encoding="utf-8").lower()
    assert "openidaes" not in registry
    assert "crafts" not in registry
    shipped = [path for path in _tracked() if path.startswith(("src/", "benchmarks/"))]
    assert not any("openidaes" in path.lower() or "crafts" in path.lower() for path in shipped)
