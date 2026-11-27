"""F2-WO6a: lowering and raising (ADR 0062 D12), E-F2-3's library half.

- **The corpus.** Every v1 revision F0 reads: M1's (T07's revision corpus, `tests/t07_corpus.py`,
  50) and the revisions of F0's run set that are not in it (`scripts/corpus_identity.py`
  `run_corpus`: its `g8` revisions are M1's; `BASIS_CASES`, 9). The `k05` runs are SYN-001
  variants the CLI solves from `benchmarks/syn001/reference_values.yaml`, not revision documents.
- **E-F2-3, library half.** Each raises to a schema-valid v2 document that lowers to the same
  bytes (ADR 0002's canonical JSON) and so to the same v1 `content_hash`; the lowered document is
  schema-valid v1.
- **Refusals.** Each non-expressible construct of D12's list is refused with the catalogued
  `construct_unavailable` naming it, exactly (one test per construct).
"""

from __future__ import annotations

import copy
import json
import sys
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml
from f2.legacy_providers import legacy_providers

from openflowsheet.application.revisions import content_hash as v1_content_hash
from openflowsheet.canonical import canonical_json
from openflowsheet.messages.catalogue import CATALOGUE
from openflowsheet.registry.tokens import Coded
from openflowsheet.revision_v2 import content_hash, parse
from openflowsheet.revision_v2.lower import (
    V1_ROLES,
    LegacyProviders,
    LoweringError,
    file_components,
    file_parameter_sets,
    legacy_records,
    lower,
)
from openflowsheet.revision_v2.raise_v1 import raise_v1
from openflowsheet.schema_check import validate_document

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import corpus_identity as gate  # noqa: E402
from t07_corpus import CORPUS  # noqa: E402

V2 = ROOT / "tests" / "fixtures" / "schemas" / "v2" / "process_revision" / "valid"
#: A SYN-001 revision of the corpus: three components, seven `nTP-v1` connections.
BASE = "SYN-001-T06-NET02"
#: A record SHA no legacy file holds.
FOREIGN = "f" * 64


def _corpus() -> dict[str, Callable[[], dict[str, Any]]]:
    found: dict[str, Callable[[], dict[str, Any]]] = dict(CORPUS)
    for run_set, name in gate.run_corpus():
        if run_set == "k05" or name in found:
            continue

        def load(run_set: str = run_set, name: str = name) -> dict[str, Any]:
            return gate.revision_document(run_set, name)

        found[name] = load
    return found


CORPUS_REVISIONS = _corpus()


@cache
def _providers() -> LegacyProviders:
    return legacy_providers()


def _raised(name: str = BASE) -> dict[str, Any]:
    return raise_v1(CORPUS_REVISIONS[name](), _providers())


def _refusals(document: dict[str, Any]) -> tuple[Coded, ...]:
    with pytest.raises(LoweringError) as caught:
        lower(parse(document), _providers())
    return caught.value.refusals


def _unavailable(*pairs: tuple[str, str]) -> tuple[Coded, ...]:
    found = [Coded("construct_unavailable", {"construct": c, "foundation": f}) for c, f in pairs]
    return tuple(sorted(found, key=Coded.sort_key))


# -- the corpus ---------------------------------------------------------------------------------


def test_e_f2_3_corpus_is_m1_and_the_run_set() -> None:
    """59 revisions: M1's 50 (which hold every `g8` run) and the 9 basis cases."""
    g8 = [name for run_set, name in gate.run_corpus() if run_set == "g8"]
    assert len(CORPUS) == 50
    assert set(g8) <= set(CORPUS)
    assert sum(len(names) for names in gate.BASIS_CASES.values()) == 9
    assert len(CORPUS_REVISIONS) == 59


@pytest.mark.parametrize("name", sorted(CORPUS_REVISIONS))
def test_e_f2_3_corpus_revision_raises_and_lowers_to_its_bytes(name: str) -> None:
    """E-F2-3 (library half): raise, parse as v2, lower; the same canonical bytes and v1 hash."""
    original = CORPUS_REVISIONS[name]()
    raised = raise_v1(original, _providers())
    lowered = lower(parse(raised), _providers())
    validate_document("process-revision.schema.json", lowered)
    assert canonical_json(lowered) == canonical_json(original)
    assert v1_content_hash(lowered) == v1_content_hash(original)
    assert original == CORPUS_REVISIONS[name](), "raising does not change its input"


def test_raise_is_the_inverse_field_map() -> None:
    """The raised document's D12 fields: the provider's native convention and id, each component's
    legacy record, `T`, no reaction set, section or override, `definition: nTP-v1`."""
    raised = _raised()
    assert raised["convention"] == "SYN-001-ref-v1"
    assert raised["property_methods"] == {"default": "syn001", "overrides": []}
    assert raised["materials"] == {"thermal_coordinate": "T", "definitions": []}
    assert (raised["reaction_sets"], raised["sections"]) == ([], {})
    records = legacy_records()
    for component in raised["component_set"]["components"]:
        found = records[component["record"]]
        assert found == ("benchmarks/syn001/components.yaml", component["id"])
    assert raised["component_set"]["parameter_sets"] == []
    for connection in raised["connections"]:
        assert connection["definition"] == "nTP-v1"
        assert "state_definition" not in connection and "component_mapping" not in connection


def test_a_stated_content_hash_names_its_own_document() -> None:
    """A v1 `content_hash` raises to the v2 document's and lowers back to the v1 one."""
    original = CORPUS_REVISIONS[BASE]()
    original["content_hash"] = v1_content_hash(original)
    raised = raise_v1(original, _providers())
    assert raised["content_hash"] == content_hash(raised) != original["content_hash"]
    lowered = lower(parse(raised), _providers())
    assert canonical_json(lowered) == canonical_json(original)


def test_an_initialization_hint_raises_and_lowers_to_its_bytes() -> None:
    """F2 review S8: no corpus revision carries `initialization_hint`, which enters `content_hash`
    and `revision.json`. Set on a corpus connection, it raises, lowers to the same canonical bytes
    and v1 hash, and a stated `content_hash` round-trips with the hint present."""
    original = CORPUS_REVISIONS[BASE]()
    guess = {
        "value": 360.0,
        "unit": "K",
        "dimension": [0, 0, 0, 1, 0, 0, 0],
        "kind": "temperature",
        "meaning": "A guess of the stream temperature",
        "role": "free",
    }
    original["connections"][1]["initialization_hint"] = {"T": guess}
    validate_document("process-revision.schema.json", original)
    without = CORPUS_REVISIONS[BASE]()
    assert v1_content_hash(original) != v1_content_hash(without)
    original["content_hash"] = v1_content_hash(original)
    raised = raise_v1(original, _providers())
    assert raised["connections"][1]["initialization_hint"] == {"T": guess}
    assert raised["content_hash"] == content_hash(raised)
    hintless = copy.deepcopy(raised)
    del hintless["connections"][1]["initialization_hint"]
    assert content_hash(hintless) != raised["content_hash"]
    lowered = lower(parse(raised), _providers())
    validate_document("process-revision.schema.json", lowered)
    assert canonical_json(lowered) == canonical_json(original)
    assert v1_content_hash(lowered) == v1_content_hash(original) == original["content_hash"]


def test_raise_refuses_a_document_outside_the_inverse() -> None:
    original = CORPUS_REVISIONS[BASE]()
    original["component_set"]["record_source"] = "benchmarks/elsewhere.yaml"
    with pytest.raises(ValueError, match="not a file of the legacy index"):
        raise_v1(original, _providers())
    original = CORPUS_REVISIONS[BASE]()
    original["component_set"]["components"].append("Z")
    with pytest.raises(ValueError, match="no record of component 'Z'"):
        raise_v1(original, _providers())


def test_lowering_leaves_its_input_unchanged() -> None:
    raised = _raised()
    revision = parse(raised)
    before = canonical_json(revision.document)
    lower(revision, _providers())
    assert canonical_json(revision.document) == before


# -- refusals, one construct each ---------------------------------------------------------------


def test_construct_unavailable_is_catalogued() -> None:
    assert "construct_unavailable" in CATALOGUE


def test_refused_convention() -> None:
    document = _raised()
    document["convention"] = "ELEMENTAL-ref-v1"
    assert _refusals(document) == _unavailable(("convention:ELEMENTAL-ref-v1", "F4"))


def test_refused_property_methods_default() -> None:
    """ADR 0050 D1 assigns `pr-c1-v1` to the C1 records only."""
    document = _raised()
    document["property_methods"]["default"] = "pr-c1-v1"
    assert _refusals(document) == _unavailable(("property_methods", "F4"))


def test_refused_property_methods_override() -> None:
    document = _raised()
    document["property_methods"]["overrides"] = [{"instance": "U-MIX", "method_set": "syn001"}]
    assert _refusals(document) == _unavailable(("property_methods", "F4"))


def test_refused_component_without_a_legacy_record() -> None:
    """One fault, one refusal (WO4-6): with no one file, the methods are not checked."""
    document = _raised()
    document["component_set"]["components"][1]["record"] = FOREIGN
    assert _refusals(document) == _unavailable(("component:B", "F4"))


def test_refused_component_named_other_than_its_record() -> None:
    document = _raised()
    components = document["component_set"]["components"]
    components[0]["record"], components[1]["record"] = (
        components[1]["record"],
        components[0]["record"],
    )
    assert _refusals(document) == _unavailable(("component:A", "F4"), ("component:B", "F4"))


def test_refused_component_set_of_two_files() -> None:
    document = _raised()
    water = next(
        sha
        for sha, record in legacy_records().items()
        if record == ("benchmarks/s05/components.yaml", "H2O")
    )
    document["component_set"]["components"].append({"id": "H2O", "record": water})
    assert _refusals(document) == _unavailable(("component_set", "F4"))


def test_a_permuted_component_set_lowers_in_its_order() -> None:
    """F2 decision WO6a-2: the set's ids in its order, as the corpus's `SYN-001-T06-STA04` (C, A, B)
    declares them; and CoolProp's one fluid of the 123 the S07 file holds."""
    assert file_components("benchmarks/syn001/components.yaml") == ("A", "B", "C")
    permuted = CORPUS_REVISIONS["SYN-001-T06-STA04"]()
    assert permuted["component_set"]["components"] == ["C", "A", "B"]
    lowered = lower(parse(raise_v1(permuted, _providers())), _providers())
    assert lowered["component_set"]["components"] == ["C", "A", "B"]
    fluids = file_components("benchmarks/s07/components.yaml")
    assert len(fluids) == 123
    one = CORPUS_REVISIONS[BASE]()
    one["component_set"] = {
        "record_source": "benchmarks/s07/components.yaml",
        "components": [fluids[5]],
    }
    raised = raise_v1(one, _providers())
    assert raised["property_methods"]["default"] == "coolprop-heos-v1"
    assert raised["convention"] == "COOLPROP-DEF-ref-v1"
    assert canonical_json(lower(parse(raised), _providers())) == canonical_json(one)


def _crystallizer() -> dict[str, Any]:
    document: dict[str, Any] = yaml.safe_load((V2 / "crystallizer.yaml").read_text("utf-8"))
    return document


def test_refused_material_definition() -> None:
    document = _raised()
    document["materials"]["definitions"] = [
        {
            "id": "abc",
            "template": "mat-v1",
            "thermal_coordinate": "T",
            "substreams": [
                {
                    "id": "liq",
                    "kind": "mixed",
                    "components": ["A", "B", "C"],
                    "conserved_basis": {"preset": "true"},
                    "grids": [],
                    "attributes": [],
                }
            ],
        }
    ]
    for connection in document["connections"][:2]:
        connection["definition"] = "abc"
        connection.pop("phase_capability", None)  # `nTP-v1` connections only (D11)
    assert _refusals(document) == _unavailable(("definition:abc", "F6"))


def _energy() -> dict[str, Any]:
    return {
        "id": "Q1",
        "kind": "energy",
        "from": {"instance": "U-HEAT", "port": "duty"},
        "to": {"instance": "U-MIX", "port": "duty"},
        "definition": "heat-v1",
    }


def _signal(**endpoints: Any) -> dict[str, Any]:
    signal = {
        "id": "X1",
        "kind": "signal",
        "from": {"instance": "U-HEAT", "port": "out"},
        "to": {"instance": "U-MIX", "port": "in"},
        "definition": "signal-v1",
        "quantity_kind": "temperature",
    }
    signal.update(endpoints)
    return signal


def test_refused_energy_connection() -> None:
    document = _raised()
    document["connections"].append(_energy())
    assert _refusals(document) == _unavailable(("energy:Q1", "F6"))


def test_refused_signal_connection() -> None:
    document = _raised()
    document["connections"].append(_signal())
    assert _refusals(document) == _unavailable(("signal:X1", "F6"))


def test_refused_probe_endpoint() -> None:
    """A probe is a signal source: its connection is refused too."""
    document = _raised()
    probe = {"probe": {"object_type": "connection", "object_id": "S1", "path": "T"}}
    document["connections"].append(_signal(**{"from": probe}))
    assert _refusals(document) == _unavailable(("probe:X1", "F6"), ("signal:X1", "F6"))


def test_refused_parameter_endpoint() -> None:
    document = _raised()
    document["connections"].append(_signal(to={"instance": "U-HEAT", "parameter": "T_out"}))
    assert _refusals(document) == _unavailable(
        ("parameter:U-HEAT.T_out", "F6"), ("signal:X1", "F6")
    )


def test_refused_reaction_set() -> None:
    document = _raised()
    document["reaction_sets"] = [
        {
            "id": "rx",
            "reactions": [
                {"id": "r1", "stoichiometry": {"A": [-1, 1], "B": [1, 1]}, "scope": ["liq"]}
            ],
        }
    ]
    assert _refusals(document) == _unavailable(("reaction_set:rx", "F6"))


def test_refused_section() -> None:
    document = _raised()
    document["sections"] = {"acme.notes": {"schema": "acme.notes", "body": {}}}
    assert _refusals(document) == _unavailable(("section:acme.notes", "F6"))


def test_refused_derived_target() -> None:
    """D10's code for a derived target."""
    document = _raised()
    document["specifications"][0]["target"] = {
        "derived": "std.mass_fraction",
        "version": "1.0.0",
        "stream": "S1",
        "component": "A",
    }
    assert _refusals(document) == _unavailable(("derived:std.mass_fraction", "F4"))


def test_refused_variable_target() -> None:
    document = _raised()
    specification = document["specifications"][0]
    specification["target"] = {"variable": "S1~T"}
    assert _refusals(document) == _unavailable((f"target:{specification['id']}", "F6"))


# -- D11 fields D12 does not classify (F2 decision WO6a-3) -------------------------------------


def test_v1_roles_are_the_v1_schema_vocabulary() -> None:
    schema = json.loads((ROOT / "schemas" / "process-revision.schema.json").read_text("utf-8"))
    roles = schema["properties"]["instances"]["items"]["properties"]["semantic_role"]["enum"]
    assert set(roles) == V1_ROLES


@pytest.mark.parametrize("role", ["utility", "controller", "shaft", "relief_device"])
def test_refused_semantic_role_outside_v1(role: str) -> None:
    document = _raised()
    document["instances"][0]["semantic_role"] = role
    assert _refusals(document) == _unavailable((f"semantic_role:{role}", "F6"))


@pytest.mark.parametrize("key", ["template", "references"])
def test_refused_instance_preview_field(key: str) -> None:
    document = _raised()
    instance = document["instances"][0]
    instance[key] = [] if key == "references" else {"id": "t"}
    assert _refusals(document) == _unavailable((f"{key}:{instance['id']}", "F6"))


def test_refused_phase_assertion() -> None:
    document = _raised()
    connection = document["connections"][0]
    connection["phase_assertion"] = "LIQUID"
    assert _refusals(document) == _unavailable((f"phase_assertion:{connection['id']}", "F5"))


#: The legacy index's one parameter-set record of `benchmarks/s10/records.yaml` (ADR 0061 D12).
S10_SET = "S10-wilson-ig-real-v1"


def _s10_set() -> str:
    from openflowsheet.records.importers.legacy import committed_index  # noqa: PLC0415

    (entry,) = (e for e in committed_index()["files"] if e["path"] == "benchmarks/s10/records.yaml")
    (record,) = (r for r in entry["records"] if r["record_type"] == "parameter_set")
    assert record["id"] == S10_SET
    return str(record["sha256"])


def test_raised_s10_document_states_the_file_parameter_set() -> None:
    """F2-R1: a raised `s10` document states the one parameter set its Wilson run reads; the
    raised SYN-001 base states none (its file has none)."""
    assert _raised("GP-C1")["component_set"]["parameter_sets"] == [_s10_set()]
    assert file_parameter_sets("benchmarks/s10/records.yaml") == (_s10_set(),)
    assert _raised()["component_set"]["parameter_sets"] == []
    assert file_parameter_sets("benchmarks/syn001/components.yaml") == ()


def test_refused_parameter_sets_other_than_the_file() -> None:
    """F2-R1: `parameter_sets` must be the file's legacy parameter-set records, no more, no less."""
    gp = _raised("GP-C1")
    gp["component_set"]["parameter_sets"] = []
    assert _refusals(gp) == _unavailable(("parameter_sets", "F4"))
    for stated in ([_s10_set()], ["0" * 64]):
        document = _raised()
        document["component_set"]["parameter_sets"] = stated
        assert _refusals(document) == _unavailable(("parameter_sets", "F4"))


def test_parameter_sets_are_not_checked_for_two_files() -> None:
    """F2-R1 / WO4-6: with records of two files, only the component refusals."""
    document = _raised()
    document["component_set"]["parameter_sets"] = [_s10_set()]
    water = next(
        sha
        for sha, record in legacy_records().items()
        if record == ("benchmarks/s05/components.yaml", "H2O")
    )
    document["component_set"]["components"].append({"id": "H2O", "record": water})
    assert _refusals(document) == _unavailable(("component_set", "F4"))


def test_refused_thermal_coordinate_other_than_t() -> None:
    """F2-R1, D12 (b): `h_mass` is refused by lowering itself (the binder lowers without
    `validate`)."""
    document = _raised()
    document["materials"]["thermal_coordinate"] = "h_mass"
    assert _refusals(document) == _unavailable(("thermal_coordinate:h_mass", "F6"))


def test_materials_are_dropped_whatever_they_hold() -> None:
    """D12: `materials` is dropped; with no `mat-v1` connection none of it reaches a v1 run."""
    document = _raised()
    document["materials"]["phase_order_keys"] = ["B"]
    lowered = lower(parse(document), _providers())
    assert canonical_json(lowered) == canonical_json(CORPUS_REVISIONS[BASE]())


def test_the_crystallizer_fixture_is_refused_construct_by_construct() -> None:
    """E-F2-2's large fixture: every construct it holds that v1 cannot express."""
    refusals = _refusals(_crystallizer())
    constructs = {c.params["construct"] for c in refusals}
    assert {c.code for c in refusals} == {"construct_unavailable"}
    assert {"definition:brine", "definition:syrup", "reaction_set:dissolution"} <= constructs
    assert any(name.startswith("component:") for name in constructs)
    assert any(name.startswith(("energy:", "signal:", "section:")) for name in constructs)


def test_lowering_refusal_lists_every_construct_once() -> None:
    document = _raised()
    document["connections"] += [_energy(), copy.deepcopy(_energy()) | {"id": "Q2"}]
    document["sections"] = {"acme.notes": {"schema": "acme.notes", "body": {}}}
    assert _refusals(document) == _unavailable(
        ("energy:Q1", "F6"), ("energy:Q2", "F6"), ("section:acme.notes", "F6")
    )
