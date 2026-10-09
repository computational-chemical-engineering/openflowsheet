"""M02 WO-12b (design note §14.5 D3/D4, §14.6 E3, §14.7 F1; ADR 0027 Amendments 3 and 4): the
registered v3 and its hard domain, gate G11v3-6 (default gate).

- **v3 is the provisional variant registered** with the selected rung's box (V5: T_in [653.15,
  693.15] K, P_in [9, 11] MPa, H2/N2 [2.5, 3.5], y_Ar + y_CH4 in [0.035, 0.2], build log D104) and
  the timeout §14.5 D4's rule gives over V5's in-rung evaluations (450 s, D104): the two documents
  differ in `variant_id`, `hard_domain` and `timeout_s` and nowhere else (§14.5 D4).
- **G11v3-6 (§14.5 D3 as amended by §14.6 E3 and §14.7 F1).** A `Boundary` built from v3's hard
  domain with the stand-in evaluation, as in WO-2:
  1. each of G11's 16 corner inlets (as `g11_coverage.py` builds them) → `out_of_domain`, with
     the violation set computed from the box: `T_K` always, `inert_min` at the 8 zero-inert
     corners, and `P_Pa` and `H2_N2` where they lie outside;
  2. each face of the box (T, P, H2/N2, `inert_max`, `inert_min`, the flow bound's two edges),
     the other dimensions at the box's centre (673.15 K, 10 MPa, 3, 0.1, F_nom), moved outward by
     10⁻⁹ relative → `out_of_domain` naming that dimension alone;
  3. each such face point moved inward by 2⁻⁴⁰ relative (§8.15) → `ok`.
"""

from __future__ import annotations

import itertools
import math

import pytest
from conftest import REPO_ROOT, load_json

from benchmarks.m02.g11_coverage import F_NOM, composition, inlet_inside
from openflowsheet.adapters import variants
from openflowsheet.canonical import file_sha256
from openflowsheet.compiled import EvaluationContext
from openflowsheet.models.c1 import COMPONENTS
from openflowsheet.models.c1.boundary import (
    Boundary,
    HardDomain,
    ReactorResult,
    hard_domain_violations,
)
from openflowsheet.models.c1.reactor_standin import CONVERSION, _standin_evaluation
from openflowsheet.thermo import StreamState
from openflowsheet.thermo.pr_c1 import PrC1Provider

V3_ID = "pymrm-6089593-g2-nz800-s123-v3"
V3 = variants.registered_variant(V3_ID)
PROVISIONAL = REPO_ROOT / "benchmarks" / "m02" / "variant-v3-provisional.json"
CHILD = REPO_ROOT / "src" / "openflowsheet" / "adapters" / "pymrm" / "child.py"
#: §14.7 F1's V5, selected by WO-12a″'s two runs (build log D104).
V5 = {
    "T_K": [653.15, 693.15],
    "P_Pa": [9.0e6, 1.1e7],
    "H2_N2": [2.5, 3.5],
    "inert_max": 0.2,
    "inert_min": 0.035,
    "tube_flow_mol_s": [0.003573480649651052, 0.014293922598604208],
}
#: The box's centre (T_in, P_in, H2/N2, y_inert; §14.7 F1: B3's), at F_nom per tube.
CENTRE = (673.15, 1.0e7, 3.0, 0.1)
OUTWARD = 1e-9
INWARD = 2.0**-40
N_TUBES = 1.0
CONTEXT = EvaluationContext(model_version="m02-wo12b", constants_sha256="0" * 64)
PROVIDER = PrC1Provider()
#: A violation message's dimension, by its prefix (`hard_domain_violations`'s messages).
PREFIXES = (
    ("T_in ", "T_K"),
    ("P_in ", "P_Pa"),
    ("H2/N2 ", "H2_N2"),
    ("inert fraction above ", "inert_max"),
    ("inert fraction below ", "inert_min"),
    ("F_ret_in ", "tube_flow_mol_s"),
)


def _named(message: str) -> set[str]:
    """The dimensions a refusal's message names (its violations, joined by "; ")."""
    found = set()
    for item in message.removeprefix("out_of_domain: ").split("; "):
        (name,) = [name for prefix, name in PREFIXES if item.startswith(prefix)]
        found.add(name)
    return found


def _evaluate(inlet: StreamState) -> ReactorResult:
    boundary = Boundary(
        provider=PROVIDER,
        n_tubes=N_TUBES,
        identity={},
        hard_domain=variants.hard_domain(V3),
    )
    return boundary.evaluate(inlet, COMPONENTS, _standin_evaluation(CONVERSION, None, 0.0), CONTEXT)


def _inlet(
    temperature: float = CENTRE[0],
    pressure: float = CENTRE[1],
    ratio: float = CENTRE[2],
    inert: float = CENTRE[3],
    flow: float = F_NOM,
) -> StreamState:
    return StreamState(
        tuple(flow * N_TUBES * y for y in composition(ratio, inert)), temperature, pressure
    )


# -- v3 as registered ----------------------------------------------------------------------------


def test_v3_is_the_provisional_variant_with_v5s_box_and_450_s() -> None:
    provisional = load_json(PROVISIONAL)
    document = load_json(
        REPO_ROOT / "src" / "openflowsheet" / "adapters" / "variants" / f"{V3_ID}.json"
    )
    assert V3.variant_id == V3_ID and not V3.synthetic
    assert V3.evaluation["runner_sha256"] == file_sha256(CHILD)
    assert V3.evaluation["profile"]["id"] == "M01-S123-v2"
    assert V3.execution["timeout_s"] == 450
    assert document["boundary"]["hard_domain"] == V5
    expected = {
        **provisional,
        "variant_id": V3_ID,
        "boundary": {**provisional["boundary"], "hard_domain": V5},
        "execution": {**provisional["execution"], "timeout_s": 450},
    }
    assert document == expected


def test_v3s_hard_domain_is_v5_with_its_floor() -> None:
    assert variants.hard_domain(V3) == HardDomain(
        temperature_k=(653.15, 693.15),
        pressure_pa=(9.0e6, 1.1e7),
        h2_n2=(2.5, 3.5),
        inert_fraction=0.2,
        tube_flow=(0.003573480649651052, 0.014293922598604208),
        inert_min=0.035,
    )


def test_the_centre_is_inside_and_evaluates_ok() -> None:
    inlet = _inlet()
    assert hard_domain_violations(inlet, variants.hard_domain(V3), N_TUBES) == []
    assert _evaluate(inlet).status == "ok"


# -- G11v3-6 (1): G11's 16 corners ---------------------------------------------------------------

CORNERS = list(itertools.product((573.15, 773.15), (5.0e6, 1.5e7), (1.0, 4.0), (0.0, 0.2)))


def _expected(inlet: StreamState) -> set[str]:
    """The violation set computed from the box (the document's numbers), not by the code under
    test: §14.6 E3's form."""
    n = inlet.n
    found = set()
    if not V5["T_K"][0] <= inlet.temperature <= V5["T_K"][1]:
        found.add("T_K")
    if not V5["P_Pa"][0] <= inlet.pressure <= V5["P_Pa"][1]:
        found.add("P_Pa")
    if not V5["H2_N2"][0] <= n[0] / n[1] <= V5["H2_N2"][1]:
        found.add("H2_N2")
    if not (n[3] + n[4]) >= V5["inert_min"] * inlet.total_flow:
        found.add("inert_min")
    if not (n[3] + n[4]) <= V5["inert_max"] * inlet.total_flow:
        found.add("inert_max")
    return found


@pytest.mark.parametrize(
    ("temperature", "pressure", "ratio", "inert"),
    CORNERS,
    ids=[f"T{t}-P{p:g}-r{r:g}-i{i:g}" for t, p, r, i in CORNERS],
)
def test_g11v3_6_each_old_corner_is_out_of_domain_naming_the_box_violations(
    temperature: float, pressure: float, ratio: float, inert: float
) -> None:
    inlet, _ = inlet_inside(temperature, pressure, ratio, inert, 1.0)
    expected = _expected(inlet)
    assert "T_K" in expected
    assert ("inert_min" in expected) == (inert == 0.0)
    assert expected == {"T_K", "P_Pa", "H2_N2"} | ({"inert_min"} if inert == 0.0 else set())
    result = _evaluate(inlet)
    assert (result.status, result.code) == ("out_of_domain", "out_of_domain")
    assert result.outlet is None
    assert _named(result.message) == expected


# -- G11v3-6 (2), (3): the box's faces -----------------------------------------------------------


def _face(name: str, side: int, move: float) -> StreamState:
    """The centre with dimension `name` at its bound `side` (0 lower, 1 upper) moved by `move`
    relative: outward for `move` = OUTWARD, inward for `move` = INWARD (§8.15's direction)."""
    if name in ("inert_max", "inert_min"):
        bound = V5[name]
        side = 1 if name == "inert_max" else 0
    else:
        bound = V5[name][side]
    sign = 1.0 if side == 1 else -1.0
    value = bound * (1.0 + sign * move) if move == OUTWARD else bound * (1.0 - sign * move)
    if name == "T_K":
        return _inlet(temperature=value)
    if name == "P_Pa":
        return _inlet(pressure=value)
    if name == "H2_N2":
        return _inlet(ratio=value)
    if name in ("inert_max", "inert_min"):
        return _inlet(inert=value)
    return _inlet(flow=value)


FACES = [
    *((name, side) for name in ("T_K", "P_Pa", "H2_N2", "tube_flow_mol_s") for side in (0, 1)),
    ("inert_max", 1),
    ("inert_min", 0),
]


@pytest.mark.parametrize(("name", "side"), FACES, ids=[f"{n}-{s}" for n, s in FACES])
def test_g11v3_6_a_face_moved_outward_is_out_of_domain_naming_it(name: str, side: int) -> None:
    result = _evaluate(_face(name, side, OUTWARD))
    assert (result.status, result.code) == ("out_of_domain", "out_of_domain")
    assert _named(result.message) == {name}


@pytest.mark.parametrize(("name", "side"), FACES, ids=[f"{n}-{s}" for n, s in FACES])
def test_g11v3_6_a_face_nudged_inward_evaluates_ok(name: str, side: int) -> None:
    inlet = _face(name, side, INWARD)
    assert hard_domain_violations(inlet, variants.hard_domain(V3), N_TUBES) == []
    result = _evaluate(inlet)
    assert result.status == "ok", result.message


def test_g11v3_6_the_floor_face_is_the_floor() -> None:
    """The inert_min face's two points straddle y_Ar + y_CH4 = 0.035 as built."""
    out, inside = _face("inert_min", 0, OUTWARD), _face("inert_min", 0, INWARD)
    for inlet, above in ((out, False), (inside, True)):
        y = (inlet.n[3] + inlet.n[4]) / inlet.total_flow
        assert (y >= 0.035) == above
        assert math.isclose(y, 0.035, rel_tol=2e-9)
