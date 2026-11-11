"""F1-WO4b (ADR 0060 D11): `check_admission`'s draft form on a schema_version 1 revision.

- **E-F1-11.** For each of F0's M1 revisions every instance is admitted; replacing one instance's
  model with one `MODEL_BASES` does not admit on the revision's basis gives `capability_missing`
  from `check_admission` and `model_unsupported` from the binder, for the same instance. F0's M1
  holds 50 revisions (`benchmarks/f0/corpus.json`), not the ADR's 49 (F1 decision W4b-5). Every
  instance of every revision is replaced once. The oracle is `MODEL_BASES`, which the registry's
  generator never reads (D6). Where the binder refuses the revision before its model check
  (`BINDER_REFUSES_FIRST`, pinned), its refusal is unchanged by the replacement and the binder half
  is vacuous (W4b-4).
- D11's basis selection on every record source, the draft form's refusals, its report schema,
  the CLI convenience, and that `model.version` is not read (W4b-2). The four transports are
  E-F1-10's fixture (`tests/test_f1_operations.py`, `DRAFT_REQUESTS`).
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
from typing import Any

import pytest
from t07_corpus import CORPUS

from openflowsheet.adapters import variants
from openflowsheet.application import capabilities
from openflowsheet.application.binding import Unbound
from openflowsheet.application.cli import API_EXIT_CODES, main
from openflowsheet.application.contract import ApplicationError
from openflowsheet.application.local import LocalApplication
from openflowsheet.application.operations import dispatch
from openflowsheet.application.revision_binding import MODEL_BASES, bind_revision_flowsheet
from openflowsheet.application.types import schema_errors
from openflowsheet.canonical import canonical_json
from openflowsheet.models.revision_flowsheet import (
    COOLPROP_RECORDS,
    IAPWS95_RECORDS,
    WILSON_RECORDS,
    component_basis,
)
from openflowsheet.registry import default_registry, usage
from openflowsheet.thermo import pr_c1

REPO_ROOT = Path(__file__).resolve().parent.parent
#: F0's M1: the revisions whose `content_hash` F0 pins (`scripts/corpus_identity.py`'s `m1`).
M1: tuple[str, ...] = tuple(
    sorted(json.loads((REPO_ROOT / "benchmarks/f0/corpus.json").read_text())["measures"]["M1"])
)
#: The M1 revisions the revision binder refuses before its `MODEL_BASES` check (the A02 family's
#: GUESS specifications, `specification_role_unsupported`; STR06's component outside the set,
#: `specification_unsupported`): they solve by the legacy route or not at all, so no replaced
#: model reaches the binder's model check there (W4b-4).
BINDER_REFUSES_FIRST: frozenset[str] = frozenset(
    {
        "SYN-001-A02-340-two-phase-guess",
        "SYN-001-A02-352-vapor-guess-410",
        "SYN-001-A02-355",
        "SYN-001-A02-355-dew-guess",
        "SYN-001-A02-355-dew-guess-377",
        "SYN-001-A02-355-liquid-guess",
        "SYN-001-A02-360",
        "SYN-001-A02-360-liquid-guess",
        "SYN-001-A02-360-no-guess",
        "SYN-001-A02-360-vapor-guess",
        "SYN-001-A02-365",
        "SYN-001-T06-STR06",
    }
)
#: Variant-backed models (M02 design note §6.1): the binder refuses an unpinned one
#: `model_variant_mismatch` before R-288's basis check, so none is a replacement.
VARIANT_BACKED: frozenset[str] = frozenset(
    variants.registered_variant(name).model_id for name in variants.registry()
)


def _report(revision: dict[str, Any]) -> dict[str, Any]:
    return capabilities.admission_report(default_registry(), revision=revision).as_document()


def _refused(revision: Any) -> dict[str, Any]:
    with LocalApplication.in_memory() as app:
        with pytest.raises(ApplicationError) as refused:
            dispatch(app, "check_admission", {"revision": revision})
    return refused.value.error.as_document()


def _replacements(basis: str) -> list[str]:
    """The models `MODEL_BASES` does not admit on `basis`, the variant-backed ones excepted."""
    return sorted(
        model
        for model, bases in MODEL_BASES.items()
        if basis not in bases and model not in VARIANT_BACKED
    )


# ================================================================================ E-F1-11


def test_m1_is_t07s_corpus() -> None:
    assert M1 == tuple(sorted(CORPUS)) and len(M1) == 50
    assert BINDER_REFUSES_FIRST <= set(M1)
    assert VARIANT_BACKED == {"c1.reactor", "c1.reactor_standin"}


@pytest.mark.parametrize("name", M1)
def test_e_f1_11_every_instance_of_an_m1_revision_is_admitted(name: str) -> None:
    revision = CORPUS[name]()
    registry = default_registry()
    basis = component_basis(revision).provider_id
    report = _report(revision)
    assert report["admitted"] is True and report["registry_sha256"] == registry.registry_sha256
    instances = [(entry["id"], entry["model"]["id"]) for entry in revision["instances"]]
    assert [(pair["instance"], pair["unit"]) for pair in report["pairs"]] == instances
    for pair in report["pairs"]:
        assert pair["admitted"] is True and pair["refusal"] is None
        assert (pair["method"], pair["definition"]) == (basis, "nTP-v1")
        assert pair["unit_version"] == registry.resolve("unit_model", pair["unit"]).version
        assert pair["method_version"] == registry.resolve("property_method", basis).version
        assert basis in MODEL_BASES[pair["unit"]]  # the independent oracle
    assert schema_errors("application-results.schema.json#/$defs/admission_report", report) == []


@pytest.mark.parametrize("name", M1)
def test_e_f1_11_a_model_not_admitted_on_the_basis_is_refused_by_both_for_one_instance(
    name: str,
) -> None:
    original = CORPUS[name]()
    basis = component_basis(original).provider_id
    replacements = _replacements(basis)
    before = bind_revision_flowsheet(copy.deepcopy(original))
    refused_first = name in BINDER_REFUSES_FIRST
    assert isinstance(before, Unbound) or not refused_first
    offset = M1.index(name)
    for index, instance in enumerate(original["instances"]):
        replacement = replacements[(offset + index) % len(replacements)]
        revision = copy.deepcopy(original)
        revision["instances"][index]["model"]["id"] = replacement
        report = _report(revision)
        assert report["admitted"] is False
        refused = [pair for pair in report["pairs"] if not pair["admitted"]]
        assert [pair["instance"] for pair in refused] == [instance["id"]]
        (pair,) = refused
        assert pair["refusal"]["code"] == "capability_missing"
        assert pair["refusal"]["params"]["unit"] == replacement
        assert pair["refusal"]["params"]["method"] == basis
        bound = bind_revision_flowsheet(revision)
        assert isinstance(bound, Unbound)
        if refused_first:
            assert isinstance(before, Unbound) and bound == before
        else:
            # R-288's refusal names the model; only the replaced instance has it.
            assert bound.detail == f"model_unsupported({replacement})"
            holders = [e["id"] for e in revision["instances"] if e["model"]["id"] == replacement]
            assert holders == [pair["instance"]]


# ============================================================================ the draft form


@pytest.mark.parametrize(
    ("source", "basis"),
    [
        (None, "syn001"),
        (pr_c1.RECORDS_PATH, "pr-c1-v1"),
        (IAPWS95_RECORDS, "iapws95-v1"),
        (WILSON_RECORDS, "wilson-ig-v2"),
    ],
)
def test_the_method_is_the_one_the_record_source_selects(source: str | None, basis: str) -> None:
    revision = CORPUS["SYN-001-nominal"]()
    if source is not None:
        revision["component_set"]["record_source"] = source
    report = _report(revision)
    assert {pair["method"] for pair in report["pairs"]} == {basis}
    for pair in report["pairs"]:
        assert pair["admitted"] == (basis in MODEL_BASES[pair["unit"]]), pair
    assert report["admitted"] == all(pair["admitted"] for pair in report["pairs"])


def test_a_coolprop_revision_takes_its_one_fluid() -> None:
    revision = CORPUS["SYN-001-nominal"]()
    revision["component_set"] = {"record_source": COOLPROP_RECORDS, "components": ["H2O"]}
    revision["instances"] = [
        {**entry, "model": {**entry["model"], "id": "thermal.heater"}}
        for entry in revision["instances"][:1]
    ]
    (pair,) = _report(revision)["pairs"]
    assert pair["method"] == "coolprop-heos-v1" and pair["admitted"] is True


def test_the_revisions_model_version_is_not_read() -> None:
    """W4b-2: pairs are taken on the highest registered versions, whatever `model.version` says."""
    revision = CORPUS["SYN-001-nominal"]()
    other = copy.deepcopy(revision)
    for entry in other["instances"]:
        entry["model"]["version"] = "9.9.9"
    assert canonical_json(_report(revision)) == canonical_json(_report(other))


def test_the_draft_form_is_a_query_not_a_use() -> None:
    with usage() as used:
        _report(CORPUS["SYN-001-nominal"]())
    assert used.sorted() == ()


def _with(member: str, value: Any) -> dict[str, Any]:
    revision = CORPUS["SYN-001-nominal"]()
    revision[member] = value
    return revision


@pytest.mark.parametrize(
    ("revision", "pointer"),
    [
        ({"title": "t"}, "/revision/schema_version"),
        (_with("schema_version", True), "/revision/schema_version"),
        (_with("schema_version", "1"), "/revision/schema_version"),
        (_with("component_set", ["A"]), "/revision/component_set"),
        (_with("instances", []), "/revision/instances"),
        (_with("instances", "U-1"), "/revision/instances"),
        (_with("instances", ["U-1"]), "/revision/instances/0"),
        (_with("instances", [{"model": {"id": "syn001.valve"}}]), "/revision/instances/0/id"),
        (
            _with("instances", [{"id": "U-1", "model": "syn001.valve"}]),
            "/revision/instances/0/model/id",
        ),
        (
            _with("instances", [{"id": "U-1", "model": {"id": ""}}]),
            "/revision/instances/0/model/id",
        ),
    ],
)
def test_a_revision_it_cannot_read_is_invalid_request_at_the_member(
    revision: dict[str, Any], pointer: str
) -> None:
    document = _refused(revision)
    assert document["code"] == "invalid_request" and document["detail"]["pointer"] == pointer


def test_a_later_schema_version_is_revision_unsupported() -> None:
    document = _refused(_with("schema_version", 2))
    assert document["code"] == "revision_unsupported"


def test_components_the_basis_refuses_are_the_binders_refusal() -> None:
    revision = CORPUS["SYN-001-nominal"]()
    revision["component_set"]["record_source"] = COOLPROP_RECORDS
    document = _refused(revision)
    assert document["code"] == "revision_unsupported"
    assert document["detail"]["unbound"] == "unsupported(components_unsupported)"
    assert "exactly one admitted fluid" in document["detail"]["hint"]
    bound = bind_revision_flowsheet(revision)
    assert isinstance(bound, Unbound) and bound.detail == "components_unsupported"


def test_an_unregistered_model_is_not_found_with_suggestions() -> None:
    revision = CORPUS["SYN-001-nominal"]()
    revision["instances"][2]["model"]["id"] = "syn001.tp_heatr"
    document = _refused(revision)
    assert document["code"] == "not_found"
    assert document["detail"]["kind"] == "unit_model"
    assert document["detail"]["id"] == "syn001.tp_heatr"
    assert "syn001.tp_heater" in document["detail"]["suggestions"]


def test_a_library_only_model_is_model_unsupported_for_its_instance() -> None:
    """D5 step 0: `syn001.cascade` is registered but not bindable; the binder's code."""
    revision = CORPUS["SYN-001-nominal"]()
    revision["instances"][0]["model"]["id"] = "syn001.cascade"
    report = _report(revision)
    refused = [pair for pair in report["pairs"] if not pair["admitted"]]
    assert [(pair["instance"], pair["refusal"]["code"]) for pair in refused] == [
        (revision["instances"][0]["id"], "model_unsupported")
    ]
    bound = bind_revision_flowsheet(revision)
    assert isinstance(bound, Unbound) and bound.detail == "model_unsupported(syn001.cascade)"


def test_the_cli_convenience_prints_the_operations_document(tmp_path: Path) -> None:
    revision = CORPUS["SYN-001-T06-NET02"]()
    revision["instances"][0]["model"]["id"] = "thermal.heater"
    path = tmp_path / "revision.json"
    path.write_text(json.dumps(revision), encoding="utf-8")
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(["admission", "--revision", str(path)])
    with LocalApplication.in_memory() as app:
        expected = dispatch(app, "check_admission", {"revision": revision})
    assert code == 0 and expected["admitted"] is False
    assert out.getvalue()[:-1].encode("utf-8") == canonical_json(expected)
    path.write_text(json.dumps({**revision, "schema_version": 2}), encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        code = main(["admission", "--revision", str(path)])
    assert code == API_EXIT_CODES["revision_unsupported"]
