"""S11 WO-A2: the routing models on every basis, the admission matrix and its typed refusals.

`docs/derivations/S11-design.md` §4.4–§4.5 (ADR 0050 D3; register R-802), assertions S11.A11–A15,
with §9's erratum to A11 (the manifests are compared with `implementation_artifact.artifact_hash`
removed: it is the module file's SHA-256, which A2's edits move), and S11.A09 at revision level.
The CoolProp cases need the optional `coolprop` extra and are skipped with a reason without it.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from m02_c1_support import connection, quantity, revision, specification
from m02_wo8_support import Solved, solve

from openflowsheet.application import revision_binding
from openflowsheet.application.binding import Unbound
from openflowsheet.application.revision_binding import (
    MODEL_BASES,
    RevisionBinding,
    _basis_refusal,
    bind_revision_flowsheet,
)
from openflowsheet.canonical import document_sha256
from openflowsheet.models.revision_flowsheet import (
    COOLPROP_RECORDS,
    IAPWS95_RECORDS,
    SYN001_BASIS,
    WILSON_BASIS,
    WILSON_RECORDS,
    component_basis,
    selectable_bases,
)
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.splitter import StreamSplitter
from openflowsheet.thermo import pr_c1, wilson_ig
from openflowsheet.thermo.pr_lib import RECORDS_PATH as PR_LIB_RECORDS

COOLPROP_AVAILABLE = importlib.util.find_spec("CoolProp") is not None
needs_coolprop = pytest.mark.skipif(
    not COOLPROP_AVAILABLE, reason="the coolprop extra is not installed (CoolProp==8.0.0)"
)

ROUTING = ("syn001.feed_source", "syn001.product_sink", "syn001.stream_splitter")
NEW = ("iapws95-v1", "coolprop-heos-v1", "wilson-ig-v1")
ROLES = {
    "syn001.feed_source": "feed",
    "syn001.product_sink": "product_sink",
    "syn001.stream_splitter": "splitter",
}


def instance(unit: str, model: str, parameters: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "id": unit,
        "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": ROLES.get(model, "other"),
        "parameters": dict(parameters or {}),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def routing_revision(
    record_source: str,
    components: Sequence[str],
    flows: Sequence[float],
    temperature: float,
    pressure: float,
    phase: str,
    split: float = 0.3,
    *,
    products_declared: bool = True,
) -> dict[str, Any]:
    """F → SP (`split_fraction` = `split`) → K1 (recycle), K2 (purge); the feed S1 pinned, every
    connection declared `phase`, or the splitter's products `vapor_liquid` (S11.A17; the feed
    source's outlet takes liquid or vapor only)."""
    declared = phase
    document = revision(
        [
            instance("F", "syn001.feed_source"),
            instance(
                "SP",
                "syn001.stream_splitter",
                {"split_fraction": quantity(split, "1", "dimensionless", [0] * 7)},
            ),
            instance("K1", "syn001.product_sink"),
            instance("K2", "syn001.product_sink"),
        ],
        [
            connection("S1", ("F", "outlet"), ("SP", "inlet"), declared),
            connection("S2", ("SP", "recycle"), ("K1", "inlet"), declared),
            connection("S3", ("SP", "purge"), ("K2", "inlet"), declared),
        ],
        [
            *(
                specification(
                    f"SPEC-S1-n-{c}", "connection", "S1", "state.n", v, "molar_flow", component=c
                )
                for c, v in zip(components, flows, strict=True)
            ),
            specification("SPEC-S1-T", "connection", "S1", "state.T", temperature, "temperature"),
            specification("SPEC-S1-P", "connection", "S1", "state.P", pressure, "pressure"),
        ],
        components=components,
        record_source=record_source,
        revision_id="S11-ROUTING-r1",
    )
    if not products_declared:
        for entry in document["connections"][1:]:
            entry["phase_capability"] = "vapor_liquid"
    return document


#: S11.A12's cases (restated, S11 rulings item 6, R-835): (record source, components, flows, T, P,
#: declared phase). The balance holds to the arithmetic of the splitter's two binary64 rows
#: (n2 = r n, n3 = (1 - r) n): within 2 ulp(n) per component, exactly 0.0 at (0.25, 0.25, 0.5),
#: and exactly -ulp(n), non-zero, at the registered non-exact state (0.4, 0.4, 0.8), which is
#: registered *because* the discrepancy is non-zero there.
CASES: Mapping[str, tuple[str, tuple[str, ...], tuple[float, ...], float, float, str]] = {
    "iapws95": (IAPWS95_RECORDS, ("H2O",), (1.0,), 300.0, 1.0e6, "liquid"),
    "coolprop": (COOLPROP_RECORDS, ("CO2",), (1.0,), 300.0, 1.0e5, "vapor"),
    "wilson": (
        WILSON_RECORDS,
        WILSON_BASIS.components,
        (0.25, 0.25, 0.5),
        330.0,
        101325.0,
        "liquid",
    ),
    "wilson-ulp": (
        WILSON_RECORDS,
        WILSON_BASIS.components,
        (0.4, 0.4, 0.8),
        330.0,
        101325.0,
        "liquid",
    ),
}
#: S11.A12's discrepancy (n2 + n3) - n per component, in units of ulp(n), where it is registered.
A12_DISCREPANCY_ULPS = {"wilson": (0.0, 0.0, 0.0), "wilson-ulp": (-1.0, -1.0, -1.0)}
CASE_PARAMS = [
    pytest.param("iapws95", id="iapws95"),
    pytest.param("coolprop", id="coolprop", marks=needs_coolprop),
    pytest.param("wilson", id="wilson"),
]
#: A12's four cases; A11 and A16 keep their three (`CASE_PARAMS`).
A12_PARAMS = [*CASE_PARAMS, pytest.param("wilson-ulp", id="wilson-ulp")]


def case_revision(case: str, *, declared: bool = True) -> dict[str, Any]:
    source, components, flows, temperature, pressure, phase = CASES[case]
    return routing_revision(
        source, components, flows, temperature, pressure, phase, products_declared=declared
    )


# -- S11.A11: SYN-001's manifests ----------------------------------------------------------------

#: `document_sha256` of each manifest with `implementation_artifact.artifact_hash` removed,
#: measured at the base `8c34ecb0` on the same constructions (§9's erratum to A11).
BASE_MANIFESTS = {
    "feed": "d062d39c043d57aea71244c60a585db594ac3065263cef6859724ddd1f072aa9",
    "sink": "f5a64b00a0484cbc9d62283e7ab5c2c609d20c82dabf3705850c56feab084a65",
    "splitter": "74a092d1b954f74c4e855c405887d1a1319517b4a457f363233b1df56c285469",
}


def _without_artifact_hash(manifest: Mapping[str, Any]) -> dict[str, Any]:
    document = copy.deepcopy(dict(manifest))
    del document["implementation_artifact"]["artifact_hash"]
    return document


def test_a11_the_syn001_manifests_are_the_bases() -> None:
    units = {
        "feed": FeedSource(unit_id="F", flows=(1.0, 0.0, 0.0), temperature=300.0, pressure=1e5),
        "sink": ProductSink(unit_id="K"),
        "splitter": StreamSplitter(unit_id="SP", split_fraction=0.3),
    }
    for name, unit in units.items():
        assert document_sha256(_without_artifact_hash(unit.manifest())) == BASE_MANIFESTS[name]


def test_a11_bound_on_syn001_the_builders_pass_nothing() -> None:
    document = routing_revision(
        "benchmarks/syn001/components.yaml", ("A", "B", "C"), (1.0, 0.0, 0.0), 300.0, 1e5, "liquid"
    )
    bound = bind_revision_flowsheet(document)
    assert isinstance(bound, RevisionBinding), bound
    for unit in bound.flowsheet.units():
        assert (unit.property_provider, unit.reference_convention, dict(unit.domain)) == (
            "syn001",
            "SYN-001-ref-v1",
            {"T": (280.0, 440.0), "P": (50000.0, 200000.0)},
        )


@pytest.mark.parametrize("case", CASE_PARAMS)
def test_a11_on_a_new_basis_the_manifest_names_the_bound_provider(case: str) -> None:
    bound = bind_revision_flowsheet(case_revision(case))
    assert isinstance(bound, RevisionBinding), bound
    basis = component_basis(case_revision(case))
    described = revision_binding.basis_provider(basis).describe()
    for unit in bound.flowsheet.units():
        manifest = unit.manifest()
        requirements, domain = manifest["execution_requirements"], manifest["validity"]["domain"]
        assert requirements["property_provider"] == described.provider_id
        assert requirements["reference_convention"] == described.reference_convention
        assert (domain["temperature_K"]["min"], domain["temperature_K"]["max"]) == tuple(
            described.domain["T"]
        )
        assert (domain["pressure_Pa"]["min"], domain["pressure_Pa"]["max"]) == tuple(
            described.domain["P"]
        )


# -- S11.A12: feed → splitter → two sinks solves on each new basis ----------------------------


def _solved(case: str) -> Solved:
    solved = solve(case_revision(case))
    assert solved.run.outcome == "CONVERGED", solved.run.message
    return solved


@pytest.mark.parametrize("case", A12_PARAMS)
def test_a12_routing_solves_on_each_new_basis(case: str) -> None:
    """S11.A12 (restated, R-835): the products are the splitter's binary64 rows exactly, and the
    balance holds within their arithmetic (2 ulp(n)); a statement about the traversal start, not
    about conservation in a state Newton moved."""
    _, components, flows, temperature, pressure, _ = CASES[case]
    state = _solved(case).run.state
    assert state is not None
    discrepancies = []
    for component, flow in zip(components, flows, strict=True):
        n2, n3 = state[f"S2.n.{component}"], state[f"S3.n.{component}"]
        assert state[f"S1.n.{component}"] == flow
        assert n2 == 0.3 * flow
        assert n3 == (1 - 0.3) * flow
        discrepancy = n2 + n3 - flow
        assert abs(discrepancy) <= 2 * math.ulp(flow)
        discrepancies.append(discrepancy / math.ulp(flow))
    if case in A12_DISCREPANCY_ULPS:
        assert tuple(discrepancies) == A12_DISCREPANCY_ULPS[case]
    for stream in ("S2", "S3"):
        assert state[f"{stream}.T"] == state["S1.T"] == temperature
        assert state[f"{stream}.P"] == state["S1.P"] == pressure


# -- S11.A09 at revision level ------------------------------------------------------------------


def test_a09_a_coolprop_revision_without_the_extra_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = importlib.util.find_spec
    monkeypatch.setattr(
        revision_binding.importlib.util,
        "find_spec",
        lambda name, *a: None if name == "CoolProp" else real(name, *a),
    )
    refused = bind_revision_flowsheet(case_revision("coolprop"))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "basis_unavailable(coolprop-heos-v1)")
    assert refused.hint == (
        "the coolprop extra is not installed (pip install openflowsheet[coolprop])"
    )


def test_a09_a_wilson_revision_without_its_records_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(wilson_ig, "_checkout_records", lambda: tmp_path / "absent.yaml")
    refused = bind_revision_flowsheet(case_revision("wilson"))
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "basis_unavailable(wilson-ig-v1)")
    assert refused.hint is not None and refused.hint.startswith("records_missing: ")


# -- S11.A13: the admission matrix and its refusals --------------------------------------------

#: §4.4's reasons, by the pair's class.
PURE_FLUID = (
    "pure-fluid units are S11b (two-phase pure-fluid streams are not representable in nTP-v1)"
)
GAMMA_PHI = "its EO face reads lnK and h_<c>; γ–φ faces are S11c"
C1_PHYSICS = "the c1.* units carry pr-c1-v1's own physics (ADR 0050 D3)"
#: SHA-256 over every refused (model, basis) pair between SYN-001 and C1, each as
#: `model|provider|detail|hint`, measured at the base `8c34ecb0` (22 pairs; the column, which the
#: base did not register, is not among them).
BASE_SYN001_C1_HINTS = "71983ce5c6c5108800dbfbe6417b1a5ec39109fe4ed6f2ba853a4b9f67b3f284"
COLUMN = "syn001.column"
COLUMN_VAPOUR = "pr-c1-v1 is vapour-only (S02 §0)"
COLUMN_PURE = "a pure fluid has no stage composition"


def test_a13_the_admission_matrix() -> None:
    for model, providers in MODEL_BASES.items():
        if model in ROUTING:
            assert providers == frozenset({"syn001", *NEW}), model
        elif model == COLUMN:
            # §5's I1 row, §9: SYN-001's basis and the Wilson registry row's provider id.
            assert providers == frozenset({"syn001", WILSON_BASIS.provider_id}), model
        elif model.startswith("syn001."):
            assert providers == frozenset({"syn001"}), model
        else:
            assert model.startswith("c1.") and providers == frozenset({"pr-c1-v1"}), model
    assert "syn001.cascade" not in MODEL_BASES


def test_a13_the_syn001_c1_hints_are_the_bases() -> None:
    c1 = component_basis({"component_set": {"record_source": pr_c1.RECORDS_PATH}})
    digest = hashlib.sha256()
    count = 0
    for model in sorted(MODEL_BASES):
        for basis in (SYN001_BASIS, c1):
            if basis.provider_id in MODEL_BASES[model] or model == COLUMN:
                continue
            refused = _basis_refusal(model, basis)
            digest.update(f"{model}|{basis.provider_id}|{refused.detail}|{refused.hint}\n".encode())
            count += 1
    assert (count, digest.hexdigest()) == (22, BASE_SYN001_C1_HINTS)
    # The column on C1's basis, a pair the base did not have: §4.4's reason.
    assert _basis_refusal(COLUMN, c1).hint == (
        f"{COLUMN} binds on the syn001 basis only, not on this revision's pr-c1-v1; "
        f"{COLUMN_VAPOUR}"
    )


def _expected_reason(model: str, provider: str) -> str | None:
    if model == COLUMN:
        return COLUMN_PURE if provider in ("iapws95-v1", "coolprop-heos-v1") else None
    if model in ROUTING or model in ("c1.feed_source", "c1.product_sink", "c1.stream_splitter"):
        return None
    if provider in ("iapws95-v1", "coolprop-heos-v1"):
        return PURE_FLUID
    return GAMMA_PHI if model.startswith("syn001.") else C1_PHYSICS


@pytest.mark.parametrize("provider", NEW)
def test_a13_every_refused_pair_on_a_new_basis_names_its_reason(provider: str) -> None:
    basis = next(b for b in selectable_bases() if b.provider_id == provider)
    namesakes = dict(revision_binding._SAME_FUNCTION)
    refused_models = sorted(m for m, on in MODEL_BASES.items() if provider not in on)
    admitted = {*ROUTING, COLUMN} if provider == WILSON_BASIS.provider_id else set(ROUTING)
    assert set(MODEL_BASES) - set(refused_models) == admitted
    for model in refused_models:
        refused = _basis_refusal(model, basis)
        own = ", ".join(sorted(MODEL_BASES[model]))
        hint = f"{model} binds on the {own} basis only, not on this revision's {provider}"
        if model in namesakes and namesakes[model] in ROUTING:
            hint += f"; on {provider} the same function is {namesakes[model]}"
        reason = _expected_reason(model, provider)
        if reason is not None:
            hint += f"; {reason}"
        assert (refused.kind, refused.detail, refused.hint) == (
            "unsupported",
            f"model_unsupported({model})",
            hint,
        )


@pytest.mark.parametrize(
    ("case", "model"),
    [
        pytest.param("iapws95", "syn001.tp_heater", id="iapws95-heater"),
        pytest.param("wilson", "syn001.tp_heater", id="wilson-heater"),
        pytest.param("wilson", "c1.stream_splitter", id="wilson-c1-splitter"),
        pytest.param("coolprop", "syn001.liquid_pump", id="coolprop-pump", marks=needs_coolprop),
    ],
)
def test_a13_the_binder_refuses_a_bound_pair(case: str, model: str) -> None:
    document = case_revision(case)
    (splitter,) = [entry for entry in document["instances"] if entry["id"] == "SP"]
    splitter["model"]["id"] = model
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert refused.detail == f"model_unsupported({model})"
    basis = component_basis(document)
    assert refused.hint == _basis_refusal(model, basis).hint
    assert refused.hint is not None and refused.hint.startswith(f"{model} binds on the ")


# -- S11.A14 / A15 --------------------------------------------------------------------------------


def test_a14_the_cascade_is_refused_with_the_column_hint() -> None:
    document = case_revision("wilson")
    (splitter,) = [entry for entry in document["instances"] if entry["id"] == "SP"]
    splitter["model"]["id"] = "syn001.cascade"
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "model_unsupported(syn001.cascade)")
    assert refused.hint == (
        "bind syn001.column with its top and bottom inlets connected (S02 §1: condenser none, "
        "reboiler none is S01's cascade)"
    )


def test_a15_pr_lib_records_select_syn001_and_are_refused() -> None:
    document = routing_revision(
        PR_LIB_RECORDS, ("H2", "N2", "Ar"), (1.0, 0.0, 0.0), 300.0, 1e5, "vapor"
    )
    assert component_basis(document) is SYN001_BASIS
    refused = bind_revision_flowsheet(document)
    assert isinstance(refused, Unbound)
    assert (refused.kind, refused.detail) == ("unsupported", "components_unsupported")
