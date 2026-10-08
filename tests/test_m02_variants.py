"""M02 WO-2 (design note §3.1, §5.1, §6.1; gates G2, G6 (b)): variants, the hard domain's per-tube
flow bound, and `ExecutionFailure` in the evaluation seam.

- **G6 (b), the pin test.** Every registered variant loads, its `document_sha256` is the
  registry's, the directory holds exactly the registered documents, and no registered document
  carries a test-only member; an out-of-process variant's `runner_sha256`, `overlay_sha256` and
  discretization estimate are the child's, the overlay's and `reference_values.yaml`'s. An edited
  document is refused, not re-pinned.
- **Resolution (§6.1).** A model reference resolves only on the registered id, the exact hash and
  the variant's own model id.
- **The stand-in variant is M01's boundary**: its boundary block holds M01's constants and its hard
  domain is `DEFAULT_HARD_DOMAIN` (no flow bound).
- **Q-F5's flow bound (ADR 0034 D10, R-232)** on a `Boundary` with the stand-in evaluation: the
  registered bounds are exactly 0.5 and 2 × the probe's nominal F_ret_in; each end is inside, one
  ulp beyond is `out_of_domain` naming F_ret_in; the bound is the last hard-domain check, after
  M01's messages; M01's own boundary has no bound (its stand-in states run at 140 × nominal).
- **`ExecutionFailure` (ADR 0033 D10)** becomes `error`, `external_<kind>`, with no outlet values;
  an unregistered kind is a `ValueError`.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from conftest import REPO_ROOT, load_json, load_yaml

from openflowsheet.adapters import variants
from openflowsheet.canonical import document_sha256, file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.boundary import (
    DATA_H2_N2,
    DATA_PRESSURE_PA,
    DATA_TEMPERATURE_K,
    DEFAULT_HARD_DOMAIN,
    DEFECT_LIMIT,
    ENVELOPE_FIELDS,
    EPS_PRESSURE,
    EXECUTION_FAILURE_KINDS,
    Boundary,
    ExecutionFailure,
    HardDomain,
    ReactorResult,
    TubeInlet,
    hard_domain_violations,
)
from openflowsheet.models.c1.reactor_standin import CONVERSION, _standin_evaluation
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

VARIANT_DIR = REPO_ROOT / "src" / "openflowsheet" / "adapters" / "variants"
STANDIN_ID = "standin-x025-v1"
PROBE: dict[str, Any] = load_json(REPO_ROOT / "benchmarks" / "m01" / "reactor-probe.json")
F_NOM: float = PROBE["pinned"]["F_ret_in_mol_s"]
#: R-232: the real reactor's variant's per-tube flow bound, as registered in the note (§3.1).
FLOW_BOUND = (0.003573480649651052, 0.014293922598604208)
CONTEXT = EvaluationContext(model_version="m02-variants", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
#: A nominal C1 inlet (M01 spec §8.15: y_NH3 = 0.03, H2/N2 = 3, Ar:CH4 = 3:4), 673.15 K, 10 MPa.
Y_NOMINAL = (0.6975, 0.2325, 0.03, 0.017142857142857144, 0.022857142857142857)
TEST_ONLY = ("perturbation_mol_s", "pressure_drop_Pa")


def _inlet(per_tube_flow: float, n_tubes: float) -> StreamState:
    total = per_tube_flow * n_tubes
    return StreamState(n=tuple(total * y for y in Y_NOMINAL), temperature=673.15, pressure=1.0e7)


def _boundary(domain: HardDomain, n_tubes: float) -> Boundary:
    return Boundary(provider=PROVIDER, n_tubes=n_tubes, identity={}, hard_domain=domain)


def _evaluate(boundary: Boundary, inlet: StreamState) -> ReactorResult:
    return boundary.evaluate(inlet, COMPONENTS, _standin_evaluation(CONVERSION, None, 0.0), CONTEXT)


# -- G6 (b): the pin test ------------------------------------------------------------------------


def test_g6b_every_registered_variant_loads_at_its_pinned_hash() -> None:
    registered = variants.registry()
    assert STANDIN_ID in registered
    documents = sorted(path.name for path in VARIANT_DIR.glob("*.json"))
    assert documents == sorted([variants.REGISTRY_FILE, *(f"{key}.json" for key in registered)])
    reference = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")
    estimate = reference["derived_from_measured"]["discretization_estimate"]
    for variant_id, pinned in registered.items():
        variant = variants.registered_variant(variant_id)
        document = load_json(VARIANT_DIR / f"{variant_id}.json")
        assert variant.sha256 == document_sha256(document) == pinned
        assert not set(TEST_ONLY) & set(variant.evaluation), "a test-only member is registered"
        if variant.kind == "out_of_process":
            child = REPO_ROOT / "src" / "openflowsheet" / "adapters" / "pymrm" / "child.py"
            assert variant.evaluation["runner_sha256"] == file_sha256(child)
            overlay = REPO_ROOT / "benchmarks" / "m01" / "reactor-overlay.json"
            assert variant.evaluation["overlay_sha256"] == file_sha256(overlay)
            assert variant.accuracy["discretization_estimate"] == estimate
            assert not variant.synthetic


@pytest.fixture
def edited_registry(tmp_path: Path) -> Iterator[Path]:
    """`variants.VARIANTS` pointed at a copy of the registered directory, caches emptied."""
    for path in VARIANT_DIR.glob("*.json"):
        (tmp_path / path.name).write_bytes(path.read_bytes())
    saved = variants.VARIANTS
    variants.VARIANTS = tmp_path  # type: ignore[misc]
    variants.registry.cache_clear()
    variants.registered_variant.cache_clear()
    try:
        yield tmp_path
    finally:
        variants.VARIANTS = saved  # type: ignore[misc]
        variants.registry.cache_clear()
        variants.registered_variant.cache_clear()


def test_g6b_an_edited_registered_document_is_refused(edited_registry: Path) -> None:
    path = edited_registry / f"{STANDIN_ID}.json"
    document = json.loads(path.read_text())
    document["coupling"]["max_outer"] = 16
    path.write_text(json.dumps(document, indent=2) + "\n")
    with pytest.raises(variants.VariantError, match="never edited"):
        variants.registered_variant(STANDIN_ID)


def test_a_document_must_be_canonical_and_schema_valid() -> None:
    document = load_json(VARIANT_DIR / f"{STANDIN_ID}.json")
    with pytest.raises(variants.VariantError, match="not canonical"):
        variants.variant_from_document({**document, "accuracy": {"precision_floor_rel": math.nan}})
    with pytest.raises(variants.VariantError, match="invalid at /execution"):
        variants.variant_from_document({**document, "execution": {"max_retries": 0}})


# -- §6.1: resolution -----------------------------------------------------------------------------


def test_g6_resolution_needs_the_registered_id_the_exact_hash_and_the_model() -> None:
    pinned = variants.registry()[STANDIN_ID]
    model = "c1.reactor_standin"
    assert variants.resolve(model, STANDIN_ID, pinned) == variants.registered_variant(STANDIN_ID)
    one_digit = ("0" if pinned[0] != "0" else "1") + pinned[1:]
    assert variants.resolve(model, STANDIN_ID, one_digit) is None
    assert variants.resolve(model, "standin-x025-v0", pinned) is None
    assert variants.resolve("c1.reactor", STANDIN_ID, pinned) is None
    assert variants.resolve(model, None, pinned) is None
    assert variants.resolve(model, STANDIN_ID, None) is None


# -- the stand-in variant is M01's boundary --------------------------------------------------------


def test_the_standin_variant_declares_m01s_boundary() -> None:
    variant = variants.registered_variant(STANDIN_ID)
    assert variant.model_id == "c1.reactor_standin" and variant.synthetic
    assert variant.kind == "in_process" and variant.sweep_ratio == 1.0
    assert variant.evaluation["conversion_N2"] == CONVERSION
    boundary = variant.boundary
    assert boundary["eps_P"] == EPS_PRESSURE and boundary["defect_limit"] == DEFECT_LIMIT
    assert boundary["provider"] == PROVIDER.describe().provider_id
    assert boundary["reference_convention"] == PROVIDER.describe().reference_convention
    assert variants.hard_domain(variant) == DEFAULT_HARD_DOMAIN
    assert DEFAULT_HARD_DOMAIN.tube_flow is None
    data = boundary["data_domain"]
    assert (tuple(data["T_K"]), tuple(data["P_Pa"]), tuple(data["H2_N2"])) == (
        DATA_TEMPERATURE_K,
        DATA_PRESSURE_PA,
        DATA_H2_N2,
    )
    assert variant.execution == {"timeout_s": None, "max_retries": 0, "kill_grace_s": None}


# -- Q-F5: the per-tube flow bound ----------------------------------------------------------------


def test_qf5_the_registered_bound_is_half_and_twice_the_probes_nominal_flow() -> None:
    assert F_NOM == 0.007146961299302104
    assert FLOW_BOUND == (0.5 * F_NOM, 2.0 * F_NOM)


@pytest.mark.parametrize("n_tubes", [1.0, 1000.0])
def test_qf5_each_end_is_inside_and_beyond_either_is_out_of_domain(n_tubes: float) -> None:
    domain = HardDomain(tube_flow=FLOW_BOUND)
    boundary = _boundary(domain, n_tubes)
    low, high = FLOW_BOUND
    for flow in (low, F_NOM, high):
        inlet = _inlet(flow, n_tubes)
        result = _evaluate(boundary, inlet)
        per_tube = inlet.total_flow / n_tubes
        assert (result.status == "ok") == (low <= per_tube <= high), (flow, per_tube)
        if n_tubes == 1.0:
            assert result.status == "ok", flow
    for flow in (math.nextafter(low, 0.0) * 0.999999, math.nextafter(high, math.inf) * 1.000001):
        result = _evaluate(boundary, _inlet(flow, n_tubes))
        assert (result.status, result.code) == ("out_of_domain", "out_of_domain")
        assert "F_ret_in" in result.message and result.outlet is None


def test_qf5_the_bound_is_judged_on_the_tube_flow_exactly_as_tube_inlet_forms_it() -> None:
    """One ulp: an inlet whose n_tot / N_tubes is the bound's lower end exactly is inside, the
    next double below is outside."""
    low = FLOW_BOUND[0]
    inside = StreamState(n=(low, 0.0, 0.0, 0.0, 0.0), temperature=673.15, pressure=1.0e7)
    outside = StreamState(
        n=(math.nextafter(low, 0.0), 0.0, 0.0, 0.0, 0.0), temperature=673.15, pressure=1.0e7
    )
    domain = HardDomain(tube_flow=FLOW_BOUND)
    assert not any(v.startswith("F_ret_in") for v in hard_domain_violations(inside, domain, 1.0))
    (flow,) = [v for v in hard_domain_violations(outside, domain, 1.0) if v.startswith("F_ret_in")]
    assert flow == f"F_ret_in {math.nextafter(low, 0.0)!r} mol/s outside {list(FLOW_BOUND)}"
    with pytest.raises(ValueError, match="needs n_tubes"):
        hard_domain_violations(inside, domain)


def test_qf5_the_flow_bound_is_the_last_hard_domain_check() -> None:
    inlet = StreamState(
        n=tuple(10.0 * F_NOM * y for y in Y_NOMINAL), temperature=473.15, pressure=1.0e7
    )
    violated = hard_domain_violations(inlet, HardDomain(tube_flow=FLOW_BOUND), 1.0)
    assert violated[0] == hard_domain_violations(inlet)[0]
    assert violated[0].startswith("T_in") and violated[-1].startswith("F_ret_in")
    assert len(violated) == len(hard_domain_violations(inlet)) + 1


def test_qf5_m01s_boundary_has_no_flow_bound() -> None:
    """M01.A25's stand-in inlet runs at about 140 × nominal per tube: still `ok` by default."""
    standin = load_yaml(REPO_ROOT / "benchmarks" / "m01" / "reference_values.yaml")["closed_form"][
        "boundary"
    ]["standin"]
    inlet = StreamState(
        n=tuple(standin["inlet_n_mol_s"]),
        temperature=standin["T_in_K"],
        pressure=standin["P_in_Pa"],
    )
    assert inlet.total_flow > 100.0 * F_NOM
    result = _evaluate(_boundary(DEFAULT_HARD_DOMAIN, 1.0), inlet)
    assert result.status == "ok"
    refused = _evaluate(_boundary(HardDomain(tube_flow=FLOW_BOUND), 1.0), inlet)
    assert refused.status == "out_of_domain" and "F_ret_in" in refused.message


# -- ADR 0033 D10: ExecutionFailure ---------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(EXECUTION_FAILURE_KINDS))
def test_an_execution_failure_is_an_error_with_no_outlet_values(kind: str) -> None:
    def failing(tube: TubeInlet) -> ExecutionFailure:
        return ExecutionFailure(kind, f"the child did not answer ({kind})")

    result = _boundary(DEFAULT_HARD_DOMAIN, 1.0).evaluate(
        _inlet(F_NOM, 1.0), COMPONENTS, failing, CONTEXT
    )
    assert (result.status, result.code) == ("error", f"external_{kind}")
    assert result.message == f"external_{kind}: the child did not answer ({kind})"
    assert all(
        getattr(result, name) is None
        for name in ENVELOPE_FIELDS
        if name not in ("status", "code", "message", "identity")
    )


def test_an_execution_failure_kind_is_registered() -> None:
    assert "cancelled" not in EXECUTION_FAILURE_KINDS  # an interrupt propagates
    with pytest.raises(ValueError, match="ExecutionFailure.kind"):
        ExecutionFailure("exploded", "")
