"""M02's join: the eight C1 models in the shared registry, each on its own basis (design note
§14.3 C1, §14.4 D3 and D5; register R-280, R-288; `docs/derivations/M06-W27-registration.md`
§21.8 J1).

- **R-288 / J1.** `MODEL_BASES` (model id -> provider ids) is the one source of which basis
  accepts which model: `set(MODEL_BASES) == set(MODEL_BUILDERS)`, each `syn001.*` model on
  SYN-001's basis and each `c1.*` model on the C1 basis. The binder's `model_unsupported(<id>)`
  pass reads it, its hint naming the same-function model of the other basis.
  `SELECTABLE_BASES` is every basis `component_basis` returns, and `basis_provider(b)` describes
  `b`'s provider id and components.
- **R-280.** All twenty-one models pinned here (the `syn001.` literals of
  `test_t05_w1b_revision` and `test_t08_kinetic_cstr` are unchanged, B13's rule); the C1 corpus
  (`m02_c1_corpus`) is registered, equals the builders it names, and binds every C1 model; every
  T07 corpus revision is on SYN-001's basis (G2 (i)).
- **R-280 (b).** The two re-taken `list_models` response fixtures decompose onto their pre-M02
  versions: with the `c1.` entries stripped they are the pre-M02 documents (R-234's method).
"""

from __future__ import annotations

import copy
import hashlib
import json
from typing import Any

import pytest
from conftest import REPO_ROOT
from m02_c1_corpus import C1_CORPUS, FILES, surrogates
from m02_c1_support import connection, feed_specifications, instance, revision
from m02_wo8_support import flash_revision
from t07_corpus import CORPUS
from test_m02_wo8_g7 import FLASH, VAPOUR_FEED_T
from test_m02_wo8_units import minimal
from test_m02_wo9_reactor import NOMINAL, reactor_revision
from test_schemas_p01 import validator_for

from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    MODEL_BUILDERS,
    MODEL_SIGNATURES,
    SELECTABLE_BASES,
    RevisionBinding,
    basis_provider,
    bind_revision_flowsheet,
)
from openflowsheet.canonical import canonical_json
from openflowsheet.models.revision_flowsheet import SYN001_BASIS, component_basis
from openflowsheet.thermo.pr_c1 import COMPONENTS

SYN001 = frozenset({"syn001"})
C1 = frozenset({"pr-c1-v1"})

#: R-288: the twenty-one models and the bases each binds on.
REGISTERED: dict[str, frozenset[str]] = {
    "syn001.feed_source": SYN001,
    "syn001.adiabatic_mixer": SYN001,
    "syn001.tp_heater": SYN001,
    "syn001.tp_flash": SYN001,
    "syn001.stream_splitter": SYN001,
    "syn001.product_sink": SYN001,
    "syn001.ph_flash": SYN001,
    "syn001.valve": SYN001,
    "syn001.liquid_pump": SYN001,
    "syn001.conversion_reactor": SYN001,
    "syn001.component_separator": SYN001,
    "syn001.heat_exchanger": SYN001,
    "syn001.kinetic_cstr": SYN001,
    "c1.feed_source": C1,
    "c1.adiabatic_mixer": C1,
    "c1.tp_heater": C1,
    "c1.tp_flash": C1,
    "c1.stream_splitter": C1,
    "c1.product_sink": C1,
    "c1.reactor": C1,
    "c1.reactor_standin": C1,
}


# -- R-288 / J1: the tables ----------------------------------------------------------------------


def test_the_registry_holds_the_twenty_one_models_each_on_its_own_basis() -> None:
    assert dict(MODEL_BASES) == REGISTERED
    assert set(MODEL_BASES) == set(MODEL_BUILDERS) == set(MODEL_SIGNATURES)


def test_the_selectable_bases_are_what_component_basis_returns() -> None:
    c1_basis = component_basis(C1_CORPUS["C1-LOOP-M02-v1"]())
    assert tuple(SELECTABLE_BASES) == (SYN001_BASIS, c1_basis)
    assert len(SELECTABLE_BASES) == 2 and SELECTABLE_BASES[1] == c1_basis
    for basis in SELECTABLE_BASES:
        described = basis_provider(basis).describe()
        assert described.provider_id == basis.provider_id
        assert tuple(described.components) == basis.components
    named = {provider for providers in MODEL_BASES.values() for provider in providers}
    assert named == {basis.provider_id for basis in SELECTABLE_BASES}


def test_g2_i_every_t07_corpus_revision_is_on_syn001s_basis() -> None:
    """§14.4 D3: G2 is unaffected by R-288 because no T07 corpus revision is on the C1 basis."""
    assert len(CORPUS) == 50
    for name, build in CORPUS.items():
        assert component_basis(build()) == SYN001_BASIS, name


# -- R-288: the binder's refusal ------------------------------------------------------------------


def _as(entry: dict[str, Any], model: str) -> dict[str, Any]:
    """`entry` naming `model` instead (its `semantic_role` is the same function's)."""
    changed = copy.deepcopy(entry)
    changed["model"]["id"] = model
    return changed


def test_syn001s_feed_to_sink_is_refused_on_the_c1_basis() -> None:
    """The probe of R-288's evidence: at `2587f14` this bound and traversed."""
    document = revision(
        [
            _as(instance("F", "c1.feed_source"), "syn001.feed_source"),
            _as(instance("K", "c1.product_sink"), "syn001.product_sink"),
        ],
        [connection("S1", ("F", "outlet"), ("K", "inlet"))],
        feed_specifications("S1", (0.6, 0.2, 0.165, 0.015, 0.02), 673.15, 1.0e7),
    )
    assert bind_revision_flowsheet(document) == Unbound(
        "unsupported",
        "model_unsupported(syn001.feed_source)",
        hint=(
            "syn001.feed_source binds on the syn001 basis only, not on this revision's "
            "pr-c1-v1; on pr-c1-v1 the same function is c1.feed_source"
        ),
    )


def test_syn001s_splitter_is_refused_on_the_c1_basis() -> None:
    """A C1 feed through `syn001.stream_splitter` into C1 sinks: bound and traversed at
    `2587f14`; refused for its model now."""
    document = minimal("c1.stream_splitter")
    (splitter,) = [entry for entry in document["instances"] if entry["id"] == "U"]
    splitter["model"]["id"] = "syn001.stream_splitter"
    assert bind_revision_flowsheet(document) == Unbound(
        "unsupported",
        "model_unsupported(syn001.stream_splitter)",
        hint=(
            "syn001.stream_splitter binds on the syn001 basis only, not on this revision's "
            "pr-c1-v1; on pr-c1-v1 the same function is c1.stream_splitter"
        ),
    )


def test_a_model_with_no_same_function_model_on_the_other_basis_names_none() -> None:
    document = minimal("c1.tp_heater")
    (heater,) = [entry for entry in document["instances"] if entry["id"] == "U"]
    heater["model"]["id"] = "syn001.valve"
    assert bind_revision_flowsheet(document) == Unbound(
        "unsupported",
        "model_unsupported(syn001.valve)",
        hint="syn001.valve binds on the syn001 basis only, not on this revision's pr-c1-v1",
    )


# -- R-280 (a): the registered C1 corpus ----------------------------------------------------------


def _built() -> dict[str, dict[str, Any]]:
    """What each registered C1 revision says it equals (its provenance's builder)."""
    f1 = FLASH["F1"]
    return {
        "C1-FLASH-F1-M02-v1": flash_revision(
            tuple(f1["n_mol_s"]), f1["T_K"], f1["P_Pa"], feed_temperature=VAPOUR_FEED_T
        ),
        "C1-HEATER-M02-v1": minimal("c1.tp_heater"),
        "C1-MIXER-M02-v1": minimal("c1.adiabatic_mixer"),
        "C1-REACTOR-M02-v1": reactor_revision(NOMINAL, model="c1.reactor"),
    }


#: The members a registered C1 revision sets itself; everything else is its builder's.
OWN = ("revision_id", "title", "description", "provenance")


@pytest.mark.parametrize("name", sorted(C1_CORPUS))
def test_each_c1_corpus_revision_is_registered_valid_and_binds(name: str) -> None:
    text = FILES[name].read_text(encoding="utf-8")
    document = json.loads(text)
    assert text == json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert document["revision_id"] == name
    assert [e.message for e in validator_for("process_revision").iter_errors(document)] == []
    assert document["component_set"]["components"] == list(COMPONENTS)
    assert isinstance(bind_revision_flowsheet(document, surrogates=surrogates), RevisionBinding)
    built = _built().get(name)
    if built is not None:  # C1-LOOP-M02-v1 is §8.1's, checked by test_m02_wo9_reactor
        own = {key: document[key] for key in OWN}
        assert {**built, **own} == document


def test_the_c1_corpus_binds_an_instance_of_every_c1_model() -> None:
    models: set[str] = set()
    for build in C1_CORPUS.values():
        binding = bind_revision_flowsheet(build(), surrogates=surrogates)
        assert isinstance(binding, RevisionBinding)
        models |= {unit.model_id for unit in binding.flowsheet.units()}
    assert models == {model for model, bases in REGISTERED.items() if bases == C1}


# -- R-280 (b): the re-taken list_models fixtures decompose onto the pre-M02 ones -----------------

FIXTURES = REPO_ROOT / "tests" / "fixtures" / "schemas" / "application_results"
#: SHA-256 of the canonical JSON of the pre-M02 fixtures (`a10dac3`'s files, whose bytes hash to
#: `d9a7f507…` and `10616e03…`).
PRE_M02_REGISTERED_MODELS = "4a60f5a3ad5def32a872407a75255370249560036e5718c848803637b2a5123a"
PRE_M02_PIN_MISSING = "2b2e3ff93067efa11aee92839d5da63aa6f5901832aeab751ee4faba5974859d"


def _sha(document: Any) -> str:
    return hashlib.sha256(canonical_json(document)).hexdigest()


def _without_c1(registry: dict[str, Any]) -> dict[str, Any]:
    return {
        **registry,
        "models": [m for m in registry["models"] if not m["model_id"].startswith("c1.")],
    }


def test_the_list_models_fixtures_decompose_onto_the_pre_m02_ones() -> None:
    view = FIXTURES / "model_registry_view"
    valid = json.loads((view / "valid" / "registered_models.json").read_text("utf-8"))
    invalid = json.loads((view / "invalid" / "pin_missing_specifications.json").read_text("utf-8"))
    c1 = sorted(m["model_id"] for m in valid["models"] if m["model_id"].startswith("c1."))
    assert c1 == sorted(model for model, bases in REGISTERED.items() if bases == C1)
    assert _sha(_without_c1(valid)) == PRE_M02_REGISTERED_MODELS
    # The invalid fixture removes the first pin's `specifications` (its generator's rule); since
    # the join that pin is `c1.feed_source`'s, so stripping the C1 entries leaves the valid
    # pre-M02 registry, and the same rule applied to it gives the pre-M02 invalid fixture.
    (first,) = [m for m in invalid["document"]["models"] if m["pins"]][:1]
    assert first["model_id"] == "c1.feed_source" and "specifications" not in first["pins"][0]
    assert _sha(_without_c1(invalid["document"])) == PRE_M02_REGISTERED_MODELS
    again = copy.deepcopy(_without_c1(valid))
    (pinned,) = [m for m in again["models"] if m["pins"]][:1]
    del pinned["pins"][0]["specifications"]
    assert _sha({"expect_error": invalid["expect_error"], "document": again}) == PRE_M02_PIN_MISSING
