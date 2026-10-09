"""T08.A14: the typed-ends sweep (T08 release spec §6.1, §9 A14; W1.5).

Three conditions, each driven through the public operations; every end must be typed
(`unsupported`, `invalid_request`, a typed failure or a result), with `internal_error` count 0. A
path no public operation reaches is recorded with its reachability argument, not counted as a pass.

**(i) `orchestrator/rank.py::UnsupportedRankStructureError` — recorded, not a pass.** It is raised
by `eliminate_alias_rows`, which runs in the K03 tear solve (`tear.py`: the tear path, not
reachable through `solve`, and `legacy_eo`'s T02 §7.5 pre-solve) and in the verifier's alias
partition (`certificate.BoundDeclaration`, both routes). `solve_route` maps only the planner's
class (`execution.UnsupportedRankStructureError`). The rank error has two kinds of trigger:

- *structural* — a row whose every nonzero column is a pressure has a coefficient other than ±1,
  more than two columns, or two that do not cancel. Row shapes are fixed by the model builders,
  never by values: every pressure-only row of `MODEL_BUILDERS` is a copy or a declared drop (one
  inflow, one outflow, `+1`/`-1`) or a single-column specification. The test below executes that
  premise on every revision of the T07 corpus, T08's CSTR documents and M02's C1 corpus
  (`m02_c1_corpus`, R-280 (a)) that either binder binds (all twenty-one models, both binders'
  declarations), from the declaration's own affine
  coefficients, which are the verifier's Jacobian entries for these rows;
- *numerical* — the two-state mismatch spread exceeds `LINEARITY_TOLERANCE` (1e-4 Pa). On ±1
  difference rows the mismatch telescopes to the path's constant identically, so the spread is
  roundoff: of order 1e-10 Pa per row at the domain's 2e5 Pa, six orders below the tolerance.

So no public operation reaches it with the v0.1 model library; a model with a pressure ratio or a
many-pressure row would, and the test below then fails. (The sibling `SpecificationConflictError`
fires on the same 1e-2 Pa tolerance T01's STR-04 applies to the declared constants at validation.)

**(ii) R4-O2, the verifier's own failed property call.** The verifier's provider (a fresh
`Syn001Provider`, never the solve's) is made to refuse every property and flash call; on both
routes the solve ends `failed(verifier_refused)`, `unsupported`, with no bundle — the registered
default of R4-O2 (a refusal, as T07 registers it) — and not `internal_error`.

**(iii) R4-O1, Unicode noncharacters.** U+FFFE and U+FDD0 have a UTF-8 form, and R4-O1's
registered default is "accepted, unchanged". Placed as a string leaf, at a numeric leaf and as a
key at depth 2, through `preview_change`, `commit_change` and, on each committed revision,
`validate`, `get_revision`, `inspect_structure`, `diff_revisions` and `solve`: every call ends
typed and none `internal_error`.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from functools import partial
from pathlib import Path
from typing import Any

import pytest
import t08_cstr_support as cstr
from m02_c1_corpus import C1_CORPUS, surrogates
from t07_corpus import CORPUS
from t07_jobs_support import commit

import openflowsheet.verify.certificate as certificate_module
from openflowsheet.application.binding import Binding, bind_revision_or_reason
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.revision_binding import (
    MODEL_BUILDERS,
    RevisionBinding,
    bind_revision_flowsheet,
)
from openflowsheet.application.types import Change, Edit
from openflowsheet.canonical import canonical_json
from openflowsheet.graph.trace import trace_declaration
from openflowsheet.thermo.syn001 import Syn001Provider, _flash_failure

NOMINAL = "SYN-001-nominal"
LEGACY = "SYN-001-A02-360"

# -- (i) the rank error's premise ---------------------------------------------------------------


def _documents() -> dict[str, dict[str, Any]]:
    documents = {name: build() for name, build in CORPUS.items()}
    documents["T08-cstr-dormant"] = cstr.dormant_revision()
    documents["T08-cstr-liquid"] = cstr.liquid_variant_revision()
    documents["T08-ptc-r1"] = cstr.ptc_r1_revision()
    # M02's join (R-280 (a)): the C1 models' instances are registered C1 corpus revisions.
    documents |= {name: build() for name, build in C1_CORPUS.items()}
    return documents


def test_a14_i_every_pressure_only_row_is_a_copy_or_a_specification() -> None:
    documents = _documents()
    models = {i["model"]["id"] for d in documents.values() for i in d.get("instances", ())}
    assert models >= set(MODEL_BUILDERS), sorted(set(MODEL_BUILDERS) - models)
    declarations = rows = 0
    offending: list[tuple[str, str, Any]] = []
    for name, document in documents.items():
        for binder in (
            partial(bind_revision_flowsheet, surrogates=surrogates),
            bind_revision_or_reason,
        ):
            binding = binder(copy.deepcopy(document))
            if not isinstance(binding, RevisionBinding | Binding):
                continue
            declarations += 1
            declaration = trace_declaration(binding.spec)
            incidence = declaration.incidence()
            for row_id in declaration.row_ids:
                columns = set(incidence[row_id])
                kinds = {declaration.column_kinds.get(column) for column in columns}
                if not columns or kinds != {"pressure"}:
                    continue
                rows += 1
                coefficients = declaration.rows[row_id].coefficients
                nonzero = {c: v for c, v in (coefficients or {}).items() if v != 0.0}
                if not (
                    coefficients is not None
                    and set(nonzero) == columns
                    and len(nonzero) <= 2
                    and all(abs(v) == 1.0 for v in nonzero.values())
                    and (len(nonzero) == 1 or sum(nonzero.values()) == 0.0)
                ):
                    offending.append((name, row_id, coefficients))
    assert offending == []
    # Measured at `wp/T08` (W1.5): 58 declarations, 405 pressure-only rows.
    assert declarations >= 58 and rows >= 405


# -- (ii) R4-O2: the verifier's own property call fails -----------------------------------------


class _RefusingProvider(Syn001Provider):
    """The verifier's provider, refusing every property and flash call."""

    def evaluate_phase(self, request: Any, context: Any) -> Any:  # type: ignore[override]
        del context
        return self._failed(request, "out_of_domain", "injected: the verifier's own call")

    def flash(self, request: Any, context: Any) -> Any:  # type: ignore[override]
        del request, context
        return _flash_failure("out_of_domain", "injected: the verifier's own flash")


@pytest.fixture
def app(tmp_path: Path) -> Iterator[LocalApplication]:
    application = LocalApplication.create(tmp_path / "p", project_id="t08-a14")
    try:
        yield application
    finally:
        application.close()


@pytest.mark.parametrize(("name", "solve_path"), [(NOMINAL, "revision_eo"), (LEGACY, "legacy_eo")])
def test_a14_ii_a_failed_verifier_property_call_ends_verifier_refused(
    app: LocalApplication, monkeypatch: pytest.MonkeyPatch, name: str, solve_path: str
) -> None:
    monkeypatch.setattr(certificate_module, "Syn001Provider", _RefusingProvider)
    revision_id = commit(app, CORPUS[name]())
    result = app.solve(revision_id, "default")
    job = app.get_job(result.job_id)
    assert job.ending is not None
    assert (job.status, job.ending.reason) == ("failed", "verifier_refused")
    assert result.error is not None
    assert (result.error.code, result.error.message) == ("unsupported", "verifier_refused")
    assert result.error.detail["solve_path"] == solve_path
    assert result.outputs == ()
    assert not (app.files_root / "jobs" / job.job_id / "bundle").exists()


# -- (iii) R4-O1: noncharacters -----------------------------------------------------------------

NONCHARACTERS = ("￾", "a﷐b")
PLACEMENTS = ("string_leaf", "numeric_leaf", "key_at_depth_2")


def _edit(placement: str, text: str) -> Edit:
    if placement == "string_leaf":
        return Edit("set", ("title",), text)
    if placement == "numeric_leaf":
        return Edit("set", ("specifications", 0, "value"), text)
    return Edit("set", ("provenance",), {text: 1})


def _typed(application: LocalApplication, operation: str, request: Any) -> Any:
    """`dispatch`'s response, or its `ApplicationError`'s document; never another exception, and
    never `internal_error` — in a raised error or in a run result's error."""
    try:
        response = dispatch(application, operation, request)
    except ApplicationError as raised:
        document = raised.error.as_document()
        assert document["code"] != "internal_error", (operation, document)
        return document
    error = response.get("error") if isinstance(response, dict) else None
    assert not (isinstance(error, dict) and error.get("code") == "internal_error"), (
        operation,
        error,
    )
    return response


@pytest.mark.parametrize("text", NONCHARACTERS, ids=ascii)
@pytest.mark.parametrize("placement", PLACEMENTS)
def test_a14_iii_a_noncharacter_ends_typed(
    app: LocalApplication, placement: str, text: str
) -> None:
    head = commit(app, CORPUS[NOMINAL]())
    change = Change(edits=(_edit(placement, text),))
    preview = change.as_change_set(head, "unused")
    del preview["idempotency_key"]
    _typed(app, "preview_change", preview)
    result = _typed(app, "commit_change", change.as_change_set(head, f"a14-{placement}"))
    # R4-O1's default: accepted and stored unchanged, its UTF-8 bytes in the canonical form (a
    # string at a numeric leaf is a draft the validator judges, as any schema error is).
    assert result["status"] == "committed", result
    revision_id = result["revision_id"]
    stored = app.get_revision(revision_id)
    assert text.encode("utf-8") in canonical_json(stored.as_document())
    _typed(app, "get_revision", {"revision_id": revision_id})
    _typed(app, "inspect_structure", {"revision_id": revision_id})
    _typed(app, "diff_revisions", {"from_revision": head, "to_revision": revision_id})
    report = _typed(app, "validate", {"revision_id": revision_id, "task": "simulation"})
    solved = _typed(app, "solve", {"revision_id": revision_id, "policy_id": "default"})
    if placement == "string_leaf":
        assert report["status"] == "READY_FOR_SIMULATION", report
        assert (solved["error"], solved["outcome"]) == (None, "CONVERGED"), solved
        assert solved["verification_status"] == "VERIFIED"
    else:
        # A string at a numeric leaf, or a member `provenance` does not declare: a schema error,
        # so INVALID, and `solve` is refused before any job (`revision_not_ready`).
        assert report["status"] == "INVALID", report
        assert solved["code"] == "revision_not_ready", solved
