"""S11 WO-D3: the verifier's γ–φ form for the K02/T05 units (S11.A72–A74, on direct states).

`docs/derivations/S11-units-design.md` §4.8 (ADR 0051), `verify/gamma_phi_units.py`. Until the
dispatch at I1b these tests call `gamma_phi_units.revision_checks` directly, with the views of
revision documents and states the units' own evaluators produce (no solve: that is WO-D6).

- **A72** VB–VC at their registered azeotrope at 101 325 Pa (verification records) as a
  `tp_heater` outlet at the azeotropic T: temperature-degenerate, `independent_split`
  `not_applicable(temperature_degenerate)`, every table row passing and every residual row
  within its kind tolerance (the direct-state reading of VERIFIED).
- **A73** on A3's Wilson routing flowsheet and on B4's Wilson column certificates the γ–φ form
  returns exactly the first pass's `DECLARED_MIXTURE` checks.
- **A74** swapping two components' `v_i` in a Wilson lifted split makes `independent_split`
  FAIL, and the admissibility or the residual checks FAIL.

The verification records are no selectable basis, so their views are parsed with Wilson's basis
monkeypatched to name their ids (`verification_basis`); the provider is the fresh one the test
passes in.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any

import pytest
import yaml
from conftest import REPO_ROOT
from m02_c1_support import connection, quantity, revision, specification
from m02_wo8_support import solve
from s11_column_support import WILSON_CASES, column_registered, committed_case
from test_s11_routing import case_revision

from openflowsheet.application.revision_binding import RevisionBinding, bind_revision_flowsheet
from openflowsheet.compile.reference import row_values
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models import (
    Wiring,
    assemble,
    duty_id,
    flow_id,
    pressure_id,
    revision_flowsheet,
    temperature_id,
)
from openflowsheet.models.revision_flowsheet import (
    WILSON_BASIS,
    WILSON_RECORDS,
    component_basis,
    parse_revision,
)
from openflowsheet.models.syn001.cascade_solve import S01_DEFAULT_V1
from openflowsheet.models.syn001.feed import FeedSource
from openflowsheet.models.syn001.flash import TPFlash, total_flow_id
from openflowsheet.models.syn001.heater import TPHeater
from openflowsheet.models.syn001.sink import ProductSink
from openflowsheet.models.syn001.tp_state import (
    liquid_flow_id,
    liquid_total_id,
    tp_state,
    vapor_flow_id,
    vapor_total_id,
)
from openflowsheet.orchestrator.execution import ExecutionPlan
from openflowsheet.orchestrator.executor import execute_plan
from openflowsheet.orchestrator.revision import plan_revision
from openflowsheet.orchestrator.splits import lifted_splits
from openflowsheet.thermo import (
    FlashRequest,
    Phase,
    PropertyProvider,
    PropertyRequest,
    StreamState,
)
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.thermo.wilson_ig_v2 import WilsonIdealGasProviderV2
from openflowsheet.verify import CheckResult, gamma_phi_units, table
from openflowsheet.verify.certificate import CheckPolicy, fresh_provider, verify_revision
from openflowsheet.verify.checks import KIND_TOLERANCE, VerifierError

CONTEXT = EvaluationContext(model_version="S11-WO-D3@" + "0" * 64, constants_sha256="0" * 64)
TOLERANCES = CheckPolicy().tolerances
RECORDS = {
    "real": REPO_ROOT / "benchmarks" / "s10" / "records.yaml",
    "verification": REPO_ROOT / "benchmarks" / "s10" / "verification-records.yaml",
}
REFERENCE = yaml.safe_load((REPO_ROOT / "benchmarks" / "s10" / "reference_values.yaml").read_text())
P_ATM = 101_325.0
VERIFICATION = ("VA", "VB", "VC")
#: GP-C1's feed (the D1 cases'): liquid at 330 K; at 350 K two-phase on the real records.
FEED_N = (0.4, 0.3, 0.3)

Document = dict[str, Any]


def _find_azeotrope(node: Any) -> Mapping[str, float]:
    """`azeotrope_VB_VC_101325Pa` wherever the reference file registers it."""
    if isinstance(node, Mapping):
        if "azeotrope_VB_VC_101325Pa" in node:
            found: Mapping[str, float] = node["azeotrope_VB_VC_101325Pa"]
            return found
        for value in node.values():
            try:
                return _find_azeotrope(value)
            except KeyError:
                continue
    raise KeyError("azeotrope_VB_VC_101325Pa")


AZEOTROPE = _find_azeotrope(REFERENCE)


# -- the revision and the state ------------------------------------------------------------------


def _instance(unit: str, model: str, parameters: Mapping[str, Any] | None = None) -> Document:
    roles = {"syn001.feed_source": "feed", "syn001.product_sink": "product_sink"}
    return {
        "id": unit,
        "model": {"id": model, "version": "0.0.0-declared", "artifact_ref": None},
        "semantic_role": roles.get(model, "other"),
        "parameters": dict(parameters or {}),
        "policy": {"fidelity": "test", "validity": "test"},
    }


def heater_flash_revision(
    components: Sequence[str], feed_n: Sequence[float], t_feed: float, t_out: float
) -> Document:
    """GP-C1's shape on Wilson's record source: U-FEED →S1 (liquid)→ U-H →S2 (lifted)→ U-F,
    whose vapour S3 and liquid S4 go to U-V and U-L; the flash at the heater's T and P."""
    drop = {"pressure_drop": quantity(0.0, "Pa", "pressure", [-1, 1, -2, 0, 0, 0, 0])}
    pins = [
        *(
            specification(
                f"SPEC-S1-n-{c}", "connection", "S1", "state.n", v, "molar_flow", component=c
            )
            for c, v in zip(components, feed_n, strict=True)
        ),
        specification("SPEC-S1-T", "connection", "S1", "state.T", t_feed, "temperature"),
        specification("SPEC-S1-P", "connection", "S1", "state.P", P_ATM, "pressure"),
        specification("SPEC-S2-T", "connection", "S2", "state.T", t_out, "temperature"),
    ]
    for stream in ("S3", "S4"):
        pins.append(
            specification(f"SPEC-{stream}-T", "connection", stream, "state.T", t_out, "temperature")
        )
        pins.append(
            specification(f"SPEC-{stream}-P", "connection", stream, "state.P", P_ATM, "pressure")
        )
    return revision(
        [
            _instance("U-FEED", "syn001.feed_source"),
            _instance("U-H", "syn001.tp_heater", drop),
            _instance("U-F", "syn001.tp_flash", drop),
            _instance("U-V", "syn001.product_sink"),
            _instance("U-L", "syn001.product_sink"),
        ],
        [
            connection("S1", ("U-FEED", "outlet"), ("U-H", "inlet"), "liquid"),
            connection("S2", ("U-H", "outlet"), ("U-F", "inlet"), "vapor_liquid"),
            connection("S3", ("U-F", "vapor"), ("U-V", "inlet"), "vapor"),
            connection("S4", ("U-F", "liquid"), ("U-L", "inlet"), "liquid"),
        ],
        pins,
        components=components,
        record_source=WILSON_RECORDS,
        revision_id="S11-GP-VERIFIER",
    )


def _faces(provider: PropertyProvider) -> dict[str, Any]:
    described = provider.describe()
    return {
        "property_provider": described.provider_id,
        "reference_convention": described.reference_convention,
        "domain": {"T": described.domain["T"], "P": described.domain["P"]},
        "components": described.components,
    }


def _stream(stream: str, state: StreamState, components: Sequence[str]) -> dict[str, float]:
    values = {flow_id(stream, c): n for c, n in zip(components, state.n, strict=True)}
    values[temperature_id(stream)] = state.temperature
    values[pressure_id(stream)] = state.pressure
    return values


class Direct:
    """GP-C1's units, and the state their own evaluators put them at (as WO-D1's A68 case)."""

    def __init__(
        self, provider: PropertyProvider, feed_n: Sequence[float], t_feed: float, t_out: float
    ) -> None:
        faces = _faces(provider)
        components = faces["components"]
        feed = StreamState(n=tuple(feed_n), temperature=t_feed, pressure=P_ATM)
        heater = TPHeater(
            unit_id="U-H", provider=provider, outlet_temperature=t_out, context=CONTEXT, **faces
        )
        flash = TPFlash(
            unit_id="U-F",
            provider=provider,
            temperature=t_out,
            pressure=P_ATM,
            context=CONTEXT,
            **faces,
        )
        heated = heater.evaluate({"inlet": (feed,)}, CONTEXT)
        assert heated.status == "ok", heated.message
        outlet = heated.outlets["outlet"]
        split = tp_state(provider, outlet, CONTEXT)
        assert split.status == "ok" and split.vapor is not None and split.liquid is not None
        flashed = flash.evaluate({"inlet": (outlet,)}, CONTEXT)
        assert flashed.status == "ok", flashed.message
        assert heated.duty is not None and flashed.duty is not None
        vapor, liquid = flashed.outlets["vapor"], flashed.outlets["liquid"]
        self.components: tuple[str, ...] = tuple(components)
        self.state: dict[str, float] = {
            **_stream("S1", feed, components),
            **_stream("S2", outlet, components),
            **_stream("S3", vapor, components),
            **_stream("S4", liquid, components),
            total_flow_id("S3"): sum(vapor.n),
            total_flow_id("S4"): sum(liquid.n),
            duty_id("U-H"): heated.duty,
            duty_id("U-F"): flashed.duty,
        }
        for c, v, liq in zip(components, split.vapor.n, split.liquid.n, strict=True):
            self.state[vapor_flow_id("S2", c)] = v
            self.state[liquid_flow_id("S2", c)] = liq
        self.state[vapor_total_id("S2")] = sum(split.vapor.n)
        self.state[liquid_total_id("S2")] = sum(split.liquid.n)
        self.spec = assemble(
            label="S11-WO-D3",
            units=(
                FeedSource(
                    unit_id="U-FEED",
                    flows=tuple(feed_n),
                    temperature=t_feed,
                    pressure=P_ATM,
                    **faces,
                ),
                heater,
                flash,
                ProductSink(unit_id="U-V", **faces),
                ProductSink(unit_id="U-L", **faces),
            ),
            wiring={
                "U-FEED": Wiring({"outlet": ("S1",)}),
                "U-H": Wiring({"inlet": ("S1",), "outlet": ("S2",)}),
                "U-F": Wiring({"inlet": ("S2",), "vapor": ("S3",), "liquid": ("S4",)}),
                "U-V": Wiring({"inlet": ("S3",)}),
                "U-L": Wiring({"inlet": ("S4",)}),
            },
            streams=("S1", "S2", "S3", "S4"),
            components=components,
        )

    def failing_rows(self, state: Mapping[str, float]) -> dict[str, float]:
        """The residual rows outside their registered kind tolerance at `state`."""
        kinds = self.spec.row_kinds
        return {
            row: value
            for row, value in row_values(self.spec, state).items()
            if not abs(value) <= KIND_TOLERANCE[kinds[row]]
        }


@pytest.fixture
def verification_basis(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Wilson's basis naming the verification records' ids, so their revision parses."""
    basis = dataclasses.replace(
        WILSON_BASIS,
        components=VERIFICATION,
        molecular_weights=MappingProxyType(dict.fromkeys(VERIFICATION, 0.05)),
    )
    monkeypatch.setattr(revision_flowsheet, "WILSON_BASIS", basis)
    yield


def gp_checks(
    document: Document, state: Mapping[str, float], provider: PropertyProvider
) -> dict[str, CheckResult]:
    view = parse_revision(document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    checks = gamma_phi_units.revision_checks(
        view, splits, state, provider=provider, context=CONTEXT, tolerances=TOLERANCES
    )
    by_id = {check.id: check for check in checks}
    assert len(by_id) == len(checks)
    return by_id


def _not_passing(checks: Mapping[str, CheckResult]) -> dict[str, tuple[str, str]]:
    return {
        k: (c.result, c.reason)
        for k, c in checks.items()
        if c.result not in ("pass", "not_applicable")
    }


# -- S11.A72 -------------------------------------------------------------------------------------


@pytest.mark.usefixtures("verification_basis")
def test_a72_the_azeotrope_is_temperature_degenerate_and_verifies() -> None:
    provider = WilsonIdealGasProviderV2(RECORDS["verification"])
    x_vb, t_az = AZEOTROPE["x_VB"], AZEOTROPE["T"]
    feed_n = (0.0, x_vb, 1.0 - x_vb)
    direct = Direct(provider, feed_n, 330.0, t_az)
    checks = gp_checks(
        heater_flash_revision(VERIFICATION, feed_n, 330.0, t_az), direct.state, provider
    )

    for unit, stream in (("U-H", "S2"), ("U-F", "S2")):
        saturation = checks[f"phase_admissibility.{unit}.{stream}.saturation"]
        assert saturation.result == "pass"
        assert saturation.value is not None and saturation.value <= TOLERANCES["temperature"]
        assert gamma_phi_units.BAND_NOTE in (saturation.independence_qualification or "")
        independent = checks[f"independent_split.{unit}.{stream}"]
        assert (independent.result, independent.reason) == (
            "not_applicable",
            "temperature_degenerate",
        )
        assert not [k for k in checks if k.startswith(f"independent_split.{unit}.{stream}.")]
    # The heater's energy balance reads S2 from the stored split, and says so.
    energy = checks["energy_balance.U-H"]
    assert energy.result == "pass"
    assert table.SPLIT_ENTHALPY_NOTE.format(stream="S2") in (
        energy.independence_qualification or ""
    )
    assert _not_passing(checks) == {}
    assert direct.failing_rows(direct.state) == {}


# -- S11.A73 -------------------------------------------------------------------------------------


@pytest.mark.parametrize("declared", [True, False], ids=["declared", "undeclared"])
def test_a73_the_routing_flowsheet_has_the_first_passs_checks(declared: bool) -> None:
    solved = solve(case_revision("wilson"))
    assert solved.run.outcome == "CONVERGED" and solved.run.state is not None
    document = case_revision("wilson", declared=declared)
    view = parse_revision(document)
    provider = fresh_provider(component_basis(document))
    arguments: dict[str, Any] = {
        "provider": provider,
        "context": CONTEXT,
        "tolerances": TOLERANCES,
    }
    first = table.revision_checks(view, (), solved.run.state, **arguments)
    ours = gamma_phi_units.revision_checks(view, (), solved.run.state, **arguments)
    assert ours == first
    # Undeclared, the splitter's products are unlifted and owned by no registry split: blocked.
    blocked = [c.id for c in ours if c.reason.startswith("temperature_degenerate_unlifted(")]
    assert bool(blocked) is not declared


@pytest.mark.parametrize("name", WILSON_CASES)
def test_a73_the_column_certificate_has_the_first_passs_checks(
    name: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every call `verify_revision` makes to the first pass's table is answered identically by
    the γ–φ form, at the same arguments (B4's certificates; the column's staged splits are
    passed and left to its own rows)."""
    original = table.revision_checks
    calls: list[int] = []

    def both(*args: Any, **kwargs: Any) -> list[CheckResult]:
        first = original(*args, **kwargs)
        assert gamma_phi_units.revision_checks(*args, **kwargs) == first
        calls.append(len(first))
        return first

    with column_registered(monkeypatch, frozenset({"syn001", "wilson-ig-v1"})):
        document = committed_case(name)
        binding = bind_revision_flowsheet(document)
        assert isinstance(binding, RevisionBinding), binding
        plan, _ = plan_revision(binding, S01_DEFAULT_V1)
        assert isinstance(plan, ExecutionPlan), plan
        run = execute_plan(
            plan=plan, flowsheet=binding.flowsheet, spec=binding.spec, policy=S01_DEFAULT_V1
        )
        assert run.outcome == "CONVERGED", run.message
        monkeypatch.setattr(table, "revision_checks", both)
        verify_revision(binding, document, run, solve_plan=plan.steps[-1].solve_plan)
    assert calls and all(count > 0 for count in calls)


# -- S11.A74 -------------------------------------------------------------------------------------


def test_a74_swapping_two_vapour_flows_fails_the_split() -> None:
    provider = WilsonIdealGasProviderV2(RECORDS["real"])
    components = WILSON_BASIS.components
    direct = Direct(provider, FEED_N, 330.0, 350.0)
    document = heater_flash_revision(components, FEED_N, 330.0, 350.0)
    name = "U-H.S2"

    base = gp_checks(document, direct.state, provider)
    assert _not_passing(base) == {}
    assert base[f"phase_admissibility.{name}.closure"].result == "pass"
    assert direct.failing_rows(direct.state) == {}

    first, last = components[0], components[-1]
    mutated = dict(direct.state)
    mutated[vapor_flow_id("S2", first)], mutated[vapor_flow_id("S2", last)] = (
        direct.state[vapor_flow_id("S2", last)],
        direct.state[vapor_flow_id("S2", first)],
    )
    assert mutated[vapor_flow_id("S2", first)] != direct.state[vapor_flow_id("S2", first)]
    checks = gp_checks(document, mutated, provider)
    assert checks[f"independent_split.{name}.{first}"].result == "fail"
    assert checks[f"independent_split.{name}.{last}"].result == "fail"
    admissibility = checks[f"phase_admissibility.{name}.closure"]
    residuals = direct.failing_rows(mutated)
    assert admissibility.result == "fail" or residuals
    # Measured: both. The swapped vapour fails the stability test (tm −0.21), and the split's
    # own rows (`v + l = n`), its equilibrium rows and the duty rows leave tolerance.
    assert admissibility.result == "fail"
    assert {f"U-H:split:{first}", f"U-H:split:{last}"} <= set(residuals)
    assert {f"U-H:HEAT-equilibrium:{first}", f"U-H:HEAT-equilibrium:{last}"} <= set(residuals)


# -- the pieces ----------------------------------------------------------------------------------


def test_a_non_degenerate_lifted_stream_reads_the_fresh_flash() -> None:
    """The heater's S2 enthalpy is Σ phases of the fresh TP flash, mixture h per phase, with no
    note; the energy balance reads it."""
    provider = WilsonIdealGasProviderV2(RECORDS["real"])
    components = WILSON_BASIS.components
    direct = Direct(provider, FEED_N, 330.0, 350.0)
    view = parse_revision(heater_flash_revision(components, FEED_N, 330.0, 350.0))
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    found = gamma_phi_units.degeneracy(view, splits, direct.state, provider, CONTEXT)
    assert found.splits == {} and found.notes == {} and found.unlifted == frozenset()
    carried = StreamState(n=FEED_N, temperature=350.0, pressure=P_ATM)
    flashed = provider.flash(FlashRequest(state=carried), CONTEXT)
    assert flashed.vapor is not None and flashed.liquid is not None
    want = 0.0
    parts: tuple[tuple[Phase, StreamState], ...] = (
        ("VAPOR", flashed.vapor),
        ("LIQUID", flashed.liquid),
    )
    for phase, part in parts:
        h = provider.evaluate_phase(
            PropertyRequest(state=part, phase=phase, properties=("h",)), CONTEXT
        )
        want += sum(part.n) * h.values["h"]
    assert set(found.enthalpy) == {"S2"}
    assert found.enthalpy["S2"] == want


def test_a_single_phase_split_is_judged_under_its_branch_id() -> None:
    """A heater outlet below its bubble point: the split is liquid only, `.bubble` by the liquid's
    stability, and the fresh flash agrees."""
    provider = WilsonIdealGasProviderV2(RECORDS["real"])
    components = WILSON_BASIS.components
    direct = Direct(provider, FEED_N, 330.0, 335.0)
    assert direct.state[vapor_total_id("S2")] == 0.0
    checks = gp_checks(
        heater_flash_revision(components, FEED_N, 330.0, 335.0), direct.state, provider
    )
    bubble = checks["phase_admissibility.U-H.S2.bubble"]
    assert bubble.result == "pass" and bubble.tolerance is not None and bubble.tolerance > 0.0
    assert [checks[f"independent_split.U-H.S2.{c}"].result for c in components] == ["pass"] * 3
    assert _not_passing(checks) == {}


def test_only_the_registry_splits_are_added() -> None:
    view = parse_revision(heater_flash_revision(WILSON_BASIS.components, FEED_N, 330.0, 350.0))
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    assert [s.unit for s in gamma_phi_units.registry_splits(view, splits)] == ["U-H", "U-F"]
    staged = dataclasses.replace(splits[0], unit="COL:stage:1")
    assert gamma_phi_units.registry_splits(view, (*splits, staged)) == splits


def test_a_composition_independent_provider_is_refused() -> None:
    view = parse_revision(heater_flash_revision(WILSON_BASIS.components, FEED_N, 330.0, 350.0))
    with pytest.raises(VerifierError, match="composition-dependent"):
        gamma_phi_units.revision_checks(
            view, (), {}, provider=Syn001Provider(), context=CONTEXT, tolerances=TOLERANCES
        )
