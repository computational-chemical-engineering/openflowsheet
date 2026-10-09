"""M02 WO-7: C1 revisions bind on `pr-c1-v1` by `record_source`, and variant-backed models are
pinned by variant id and SHA-256 (design note §6.1, §8 *Binding*; ADR 0034 D8, ADR 0035 D1;
R-226, R-231; gate G6 (a)).

G2's half here: every `record_source` other than the C1 records' reads exactly as before (the
SYN-001 basis, the same object); the corpus-wide byte-identity is the existing T05–T07 tests'.
"""

from __future__ import annotations

from typing import Any

import pytest
from m02_c1_support import (
    connection,
    feed_specifications,
    instance,
    revision,
    specification,
)

from openflowsheet.adapters import variants
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import basis_provider, bind_revision_flowsheet
from openflowsheet.models.revision_flowsheet import (
    MOLECULAR_WEIGHTS,
    SYN001_BASIS,
    RevisionError,
    canonical_components,
    component_basis,
    parse_revision,
)
from openflowsheet.thermo.pr_c1 import COMPONENTS, RECORDS_PATH, load_records
from openflowsheet.thermo.syn001 import Syn001Provider

REAL = "pymrm-6089593-g2-nz800-s123-v1"
STANDIN = "standin-x025-v1"
FEED = (0.74625, 0.24875, 0.0, 0.002, 0.003)


def _through(model: str = "c1.reactor", **pin: Any) -> dict[str, Any]:
    """feed -> R1 (`model`) -> sink, the feed fully specified."""
    return revision(
        [
            instance("feed", "c1.feed_source"),
            instance("R1", model, **pin),
            instance("sink", "c1.product_sink"),
        ],
        [
            connection("S1", ("feed", "outlet"), ("R1", "inlet")),
            connection("S2", ("R1", "outlet"), ("sink", "inlet")),
        ],
        feed_specifications("S1", FEED, 673.15, 1.0e7),
    )


def _flipped(sha256: str) -> str:
    """`sha256` with its first hex digit changed (G6 (a): one digit)."""
    return ("1" if sha256[0] == "0" else "0") + sha256[1:]


# -- the basis ------------------------------------------------------------------------------------


def test_the_c1_records_path_selects_the_c1_basis() -> None:
    basis = component_basis({"component_set": {"record_source": RECORDS_PATH}})
    assert basis.provider_id == "pr-c1-v1"
    assert basis.components == COMPONENTS == ("H2", "N2", "NH3", "Ar", "CH4")
    assert dict(basis.molecular_weights) == {
        record.id: record.molar_mass for record in load_records().components
    }


@pytest.mark.parametrize(
    "component_set",
    [
        {},
        {"record_source": "benchmarks/syn001/components.yaml"},
        {"record_source": None},
        {"record_source": RECORDS_PATH + " "},
        {"record_source": "./" + RECORDS_PATH},
    ],
)
def test_every_other_record_source_is_syn001_exactly_as_before(component_set: Any) -> None:
    """R-231: only the exact string selects C1; everything else is SYN-001's basis object."""
    basis = component_basis({"component_set": component_set})
    assert basis is SYN001_BASIS
    assert basis.components == ("A", "B", "C")
    assert basis.molecular_weights is MOLECULAR_WEIGHTS
    assert isinstance(basis_provider(basis), Syn001Provider)


def test_a_permuted_c1_component_set_maps_onto_the_providers_order() -> None:
    basis = component_basis({"component_set": {"record_source": RECORDS_PATH}})
    assert canonical_components(["CH4", "Ar", "NH3", "N2", "H2"], basis) == COMPONENTS
    with pytest.raises(RevisionError, match="components_unsupported"):
        canonical_components(["A", "B", "C"], basis)
    # The SYN-001 basis (the default argument) refuses the C1 set, as before M02.
    with pytest.raises(RevisionError, match="components_unsupported"):
        canonical_components(list(COMPONENTS))


def test_parse_revision_reads_a_c1_revision_in_the_providers_order() -> None:
    document = _through(version=REAL, artifact_ref=variants.registry()[REAL])
    document["component_set"]["components"] = ["N2", "H2", "NH3", "CH4", "Ar"]
    view = parse_revision(document)
    assert view.components == COMPONENTS
    assert view.basis.provider_id == "pr-c1-v1"
    assert view.input_mapping.declared_components == ("N2", "H2", "NH3", "CH4", "Ar")
    reactor = {i.unit_id: i for i in view.instances}["R1"]
    assert (reactor.model_version, reactor.model_artifact_ref) == (REAL, variants.registry()[REAL])
    feed = {i.unit_id: i for i in view.instances}["feed"]
    assert (feed.model_version, feed.model_artifact_ref) == ("0.0.0-declared", None)


def test_a_c1_component_set_under_syn001s_records_is_refused_as_before() -> None:
    document = _through()
    document["component_set"]["record_source"] = "benchmarks/syn001/components.yaml"
    with pytest.raises(RevisionError, match="components_unsupported"):
        parse_revision(document)


def test_a_mass_flow_converts_with_the_c1_molar_mass() -> None:
    """`unit-conversion-v2`'s mass basis reads the C1 records' molar mass (ADR 0016 D3)."""
    document = _through(version=REAL, artifact_ref=variants.registry()[REAL])
    nh3 = load_records().components[2]
    assert nh3.id == "NH3"
    document["specifications"] = [
        entry for entry in document["specifications"] if entry["id"] != "SPEC-S1-n-NH3"
    ] + [
        specification(
            "SPEC-S1-n-NH3",
            "connection",
            "S1",
            "state.n",
            0.017031,
            "mass_flow",
            component="NH3",
        )
    ]
    view = parse_revision(document)
    (conversion,) = view.input_mapping.conversions
    assert conversion.si_value == 0.017031 / nh3.molar_mass
    feed = {i.unit_id: i for i in view.instances}["feed"]
    assert feed.pins["S1.n.NH3"] == 0.017031 / nh3.molar_mass


# -- frozen identity (G6 (a)) ---------------------------------------------------------------------


@pytest.mark.parametrize("model, name", [("c1.reactor", REAL), ("c1.reactor_standin", STANDIN)])
def test_g6a_one_hex_digit_off_is_model_variant_mismatch(model: str, name: str) -> None:
    pinned = variants.registry()[name]
    unbound = bind_revision_flowsheet(_through(model, version=name, artifact_ref=_flipped(pinned)))
    assert unbound == Unbound("unsupported", "model_variant_mismatch(R1)")


@pytest.mark.parametrize(
    "version, artifact_ref",
    [
        (None, None),
        ("0.0.0-declared", None),
        ("no-such-variant", "0" * 64),
        (STANDIN, variants.registry()[STANDIN]),  # another model's variant
    ],
)
def test_g6a_an_unknown_or_foreign_variant_is_model_variant_mismatch(
    version: str | None, artifact_ref: str | None
) -> None:
    unbound = bind_revision_flowsheet(
        _through("c1.reactor", version=version, artifact_ref=artifact_ref)  # type: ignore[arg-type]
    )
    assert unbound == Unbound("unsupported", "model_variant_mismatch(R1)")


def test_g6a_a_pinned_variant_passes_the_check() -> None:
    """With the registry's hash the check passes; what the binder says next is the builder's
    (WO-9 adds `c1.reactor`'s), never the variant's."""
    document = _through("c1.reactor", version=REAL, artifact_ref=variants.registry()[REAL])
    unbound = bind_revision_flowsheet(document)
    assert not (isinstance(unbound, Unbound) and "model_variant_mismatch" in unbound.detail)


def test_a_native_models_version_is_not_read() -> None:
    """§6.1: native models keep v0.1's behaviour — `model.version` unchecked."""
    from t07_corpus import CORPUS

    document = CORPUS["SYN-001-T06-NET03"]()
    for entry in document["instances"]:
        entry["model"]["version"] = "anything"
        entry["model"]["artifact_ref"] = "not-a-hash"
    assert not isinstance(bind_revision_flowsheet(document), Unbound)


def test_g6a_through_solve_admission() -> None:
    """G6 (a) at the API. The binder's refusal reaches `solve` through validation (T07 §5.3 step
    2): the revision cannot be analysed, so it is not READY, and admission refuses
    `revision_not_ready` with the report naming `model_variant_mismatch(R1)` — before step 3's
    `revision_unsupported`, which only a READY revision without a route reaches (build log
    D27)."""
    from openflowsheet.application.admission import admit_solve
    from openflowsheet.application.types import ApiError, Budgets, Limits, SolveBody, schema_errors

    pinned = variants.registry()[REAL]
    document = _through(version=REAL, artifact_ref=_flipped(pinned))
    error = admit_solve(
        document["revision_id"],
        document,
        SolveBody(revision_id=document["revision_id"]),
        budgets=Budgets(),
        limits=Limits(default_wall_time_s=300, max_wall_time_s=1800, max_active_jobs=4),
        active_jobs=0,
    )
    assert isinstance(error, ApiError)
    assert error.code == "revision_not_ready"
    assert schema_errors("api-error.schema.json", error.as_document()) == []
    structural = [c for c in error.detail["report"]["checks"] if c["id"].startswith("STR-")]
    assert structural
    assert all(c["result"] == "NOT_RUN" for c in structural)
    assert all("model_variant_mismatch(R1)" in c["message"] for c in structural)
