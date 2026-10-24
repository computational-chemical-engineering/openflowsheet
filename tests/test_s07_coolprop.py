"""S07.A01-A28, A32-A34 for tier A: `coolprop-heos-v1` against `s07_reference.json` (WO-S07-2a).

Every expectation is a key of `docs/derivations/scripts/s07_reference.json`, the 50-digit
evaluation of each fluid's closed form (spec §8), or of `s05_reference.json` for water (A23); the
tolerances are spec §9 and §9.1's, with S05's NC widening. The refusal probes and their answered
controls are the generator's (`probes`, spec §7). Neither generator is imported here.

Each assertion is a `*_problems` function returning what is wrong, so that the mutation battery
(A32) can run the same check against a mutated provider and require it to fail. Tests that need
CoolProp call `require_coolprop()` (spec §17.4): they skip without it, and fail under
`OPENFLOWSHEET_REQUIRE_COOLPROP=1`.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import importlib
import json
import math
import subprocess
import sys
import types
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
from s07_coolprop_support import require_coolprop

from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    Phase,
    PropertyRequest,
    PropertyResult,
    StreamState,
    pr_lib,
)
from openflowsheet.thermo import _coolprop_heos_fluids as table
from openflowsheet.thermo import coolprop_heos as cph

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "docs" / "derivations" / "scripts"
MODULE_PATH = Path(cph.__file__)
REF: dict[str, Any] = json.loads((SCRIPTS / "s07_reference.json").read_text("utf-8"))
S05: dict[str, Any] = json.loads((SCRIPTS / "s05_reference.json").read_text("utf-8"))
FLUIDS: dict[str, dict[str, Any]] = REF["fluids"]
TIER_A = [row["id"] for row in table.FLUIDS if row["tier"] == "A"]
ROWS = {row["id"]: row for row in table.FLUIDS}
CONTEXT = EvaluationContext(model_version="s07-provider", constants_sha256="0" * 64)
PROVIDERS = {cid: cph.CoolPropHeosProvider(cid) for cid in TIER_A}
NC = {"NC_V", "NC_L"}
#: The companion pressure of a Psat request (inside every fluid's box) and the jet slots by order.
PSAT_P = 1.0e5
LOW_ORDER = range(6)
THIRD_ORDER = range(6, 10)
E_SENTENCE = (
    "lower temperature bound estimated from the triple point (no melting line in CoolProp 8.0.0): "
    "T_lo = T_t*(1 + 1e-8/Pa*P_hi); solid states lie inside the box if the melting slope exceeds "
    "0.01/MPa*T_t"
)

Provider = cph.CoolPropHeosProvider
Result = PropertyResult | FlashResult


@pytest.fixture
def coolprop() -> None:
    require_coolprop()


needs_coolprop = pytest.mark.usefixtures("coolprop")


def six(cid: str) -> tuple[str, ...]:
    return ("h", "s", "v", "Z", "cp", f"lnphi_{cid}")


def ev(
    provider: Provider,
    t: float,
    p: float,
    phase: Phase,
    properties: tuple[str, ...] | None = None,
    derivatives: tuple[str, ...] | None = None,
    n: tuple[float, ...] = (1.0,),
) -> PropertyResult:
    cid = provider.describe().components[0]
    properties = six(cid) if properties is None else properties
    derivatives = ("T", "P", f"n_{cid}") if derivatives is None else derivatives
    state = StreamState(n=n, temperature=t, pressure=p)
    return provider.evaluate_phase(PropertyRequest(state, phase, properties, derivatives), CONTEXT)


def flash(
    provider: Provider,
    t: float,
    p: float,
    spec: str = "TP",
    n: tuple[float, ...] = (1.0,),
    der: tuple[str, ...] = (),
) -> FlashResult:
    state = StreamState(n=n, temperature=t, pressure=p)
    return provider.flash(FlashRequest(state, spec, der), CONTEXT)


def psat(provider: Provider, t: float) -> PropertyResult:
    cid = provider.describe().components[0]
    return ev(provider, t, PSAT_P, "LIQUID", ("Psat",), ("T", "P", f"n_{cid}"))


def tp(cid: str, name: str) -> tuple[float, float, Phase]:
    state = FLUIDS[cid]["tp_states"][name]
    phase: Phase = "LIQUID" if state["phase"] == "LIQUID" else "VAPOR"
    return state["values"][0], state["values"][1], phase


def band_t(cid: str) -> float:
    return float(FLUIDS[cid]["band"]["T"])


def refusal_problem(result: Result, status: str, code: str) -> str | None:
    """Why `result` is not the typed refusal (status, code); `None` when it is."""
    if (result.status, result.message.split(":")[0]) != (status, code):
        return f"expected {status} {code}:, got {result.status} {result.message!r}"
    if result.phase_signature is not None:
        return f"{code}: a refusal carries the phase {result.phase_signature}"
    if isinstance(result, PropertyResult) and (result.values or result.derivatives):
        return f"{code}: a refusal carries values"
    return None


def refused(result: Result, status: str, code: str) -> None:
    problem = refusal_problem(result, status, code)
    assert problem is None, problem


def value_bound(name: str, x: str, t: float, expected: float, r: float) -> float:
    """S05 A05's bound on |Δx| for state `name` (spec §9 A05), NC ×100."""
    scale = 100.0 if name in NC else 1.0
    if x == "h":
        return scale * 1e-8 * r * t
    if x == "s":
        return scale * 1e-8 * r
    if x.startswith("lnphi_"):
        return scale * 1e-8
    relative = 1e-9 if x == "v" else 1e-8
    return scale * relative * abs(expected)


def guarded(call: Callable[[], list[str]]) -> list[str]:
    """A check that raises (a missing key, a mutated signature) reports the exception."""
    try:
        return call()
    except Exception as error:  # a mutation may break a check in any way: that is a failure
        return [f"{type(error).__name__}: {error}"]


# -- the checks ------------------------------------------------------------------------------------


def a01_problems(provider: Provider, cid: str) -> list[str]:
    """Constants, canary, hashes, CAS, tier, bound and strings equal ref bitwise (A01, §16.10)."""
    ref, fluid = FLUIDS[cid], provider._fluid
    got = {
        "T_c": fluid.t_c,
        "p_c": fluid.p_c,
        "rho_c": fluid.rho_c,
        "T_lo": fluid.t_lo,
        "T_hi": fluid.t_hi,
        "P_lo": fluid.p_lo,
        "P_hi": fluid.p_hi,
        "T_sigma_max": fluid.t_sigma_max,
        "eps_sigma": fluid.eps_sigma,
        "rho_max": fluid.rho_max,
        "nc_T": list(fluid.nc_t),
        "nc_P": list(fluid.nc_p),
        "R": fluid.r,
        "M": fluid.m,
        "T_red": fluid.t_red,
        "rho_red": fluid.rho_red,
    }
    problems = [
        f"{key}: {got.get(key)!r} != ref {value!r}"
        for key, value in ref["constants"].items()
        if got.get(key) != value or [float(x).hex() for x in _flat(got[key])] != _hex(value)
    ]
    problems += [f"constant {key} not in ref" for key in set(got) - set(ref["constants"])]
    scalars = {
        "canary": fluid.canary,
        "fluid_data_sha256": fluid.fluid_data_sha256,
        "cas": fluid.cas,
        "tier": fluid.tier,
        "bound": fluid.bound,
        "name": fluid.name,
        "bibtex_eos": fluid.bibtex_eos,
        "verification": fluid.verification,
        "limitations": list(fluid.limitations),
    }
    problems += [f"{key}: {v!r} != ref" for key, v in scalars.items() if v != ref[key]]
    if fluid.component != cid:
        problems.append(f"the instance serves {fluid.component}, not {cid}")
    if cph.FLUID_DATA_SHA256.get(cid) != ref["fluid_data_sha256"]:
        problems.append("FLUID_DATA_SHA256 differs from ref")
    return problems


def _flat(value: Any) -> list[float]:
    return list(value) if isinstance(value, list | tuple) else [value]


def _hex(value: Any) -> list[str]:
    return [float(x).hex() for x in _flat(value)]


def a03_problems(module: types.ModuleType, cid: str, slots: range, bound: float) -> list[str]:
    """`helmholtz_jet` against ref `phi_states` (A03: orders ≤ 2, 1e-12; A04: third, 1e-11)."""
    problems = []
    for key, state in FLUIDS[cid]["phi_states"].items():
        ideal, residual = module.helmholtz_jet(cid, state["T"], state["rho"])
        got = list(ideal) + list(residual)
        for k in [*slots, *(10 + i for i in slots)]:
            expected = state["jet"][k]
            if not abs(got[k] - expected) <= bound * max(abs(expected), 1.0):
                problems.append(f"{key} slot {k}: {got[k]!r} vs {expected!r}")
    return problems


def a05_problems(provider: Provider, cid: str, properties: tuple[str, ...] = ()) -> list[str]:
    """`evaluate_phase` at ref `tp_states` within S05 A05's bounds (A05)."""
    problems = []
    r = FLUIDS[cid]["constants"]["R"]
    names = six(cid)
    for name, state in FLUIDS[cid]["tp_states"].items():
        t, p, phase = tp(cid, name)
        result = ev(provider, t, p, phase, names, ())
        if result.status != "ok" or result.phase_signature != phase:
            problems.append(f"{name}: {result.status} {result.message}")
            continue
        for i, x in enumerate(names):
            if properties and x not in properties:
                continue
            expected = state["values"][2 + i]
            if not abs(result.values[x] - expected) <= value_bound(name, x, t, expected, r):
                problems.append(f"{name} {x}: {result.values[x]!r} vs {expected!r}")
    return problems


def a06_problems(provider: Provider, cid: str) -> list[str]:
    problems = []
    for name, state in FLUIDS[cid]["tp_states"].items():
        t, p, phase = tp(cid, name)
        result = ev(provider, t, p, phase)
        bound = (100.0 if name in NC else 1.0) * 1e-8
        for i, x in enumerate(six(cid)):
            for wrt in ("T", "P"):
                expected = state[f"d{wrt}"][i]
                got = result.derivatives[x][wrt]
                if not abs(got - expected) <= bound * abs(expected):
                    problems.append(f"{name} d{x}/d{wrt}: {got!r} vs {expected!r}")
    return problems


def a07_problems(provider: Provider, cid: str) -> list[str]:
    problems = []
    for name in FLUIDS[cid]["tp_states"]:
        result = ev(provider, *tp(cid, name))
        for x in six(cid):
            got = result.derivatives.get(x, {})
            if got.get(f"n_{cid}") != 0.0 or f"n_{cid}" not in got:
                problems.append(f"{name} {x}: n_{cid} derivative {got.get(f'n_{cid}')!r}")
            if got.get("T") == 0.0:
                problems.append(f"{name} {x}: the control dT is 0.0")
    return problems


def a13_problems(provider: Provider, cid: str) -> list[str]:
    problems = []
    t, r = band_t(cid), FLUIDS[cid]["constants"]["R"]
    for key, probe in FLUIDS[cid]["band"]["probes"].items():
        p = float(probe["P"])
        for phase in ("LIQUID", "VAPOR"):
            result = ev(provider, t, p, phase, derivatives=())
            if phase not in probe["answered"]:
                problem = refusal_problem(result, "unsupported", "phase_not_stable")
                problems += [f"band {key} {phase}: {problem}"] if problem else []
                continue
            if result.status != "ok" or result.phase_signature != phase:
                problems.append(f"band {key} {phase}: {result.status} {result.message}")
                continue
            for i, x in enumerate(six(cid)):
                expected = probe[phase][2 + i]
                if not abs(result.values[x] - expected) <= value_bound(key, x, t, expected, r):
                    problems.append(f"band {key} {phase} {x}: {result.values[x]!r}")
    return problems


#: The status of each probe code (spec §6.5).
STATUS = {"out_of_domain": "out_of_domain", "state_length": "error"}


def request(provider: Provider, cid: str, q: list[Any]) -> Result:
    """A probe or control in the generator's compact form (`compact_request`)."""
    kind = q[0]
    if kind == "Psat":
        return psat(provider, q[1])
    if kind == "Tsat":
        return ev(provider, band_t(cid), q[1], "VAPOR", ("Tsat",))
    if kind == "flash":
        return flash(provider, q[1], q[2])
    extras = dict(zip(q[4::2], q[5::2], strict=True))
    return ev(
        provider,
        q[1],
        q[2],
        q[3],
        (extras["property"],) if "property" in extras else None,
        tuple(extras["derivatives"]) if "derivatives" in extras else None,
        tuple(extras.get("n", [1.0])),
    )


def probe_problems(provider: Provider, cid: str, tags: tuple[str, ...]) -> list[str]:
    problems, count = [], 0
    for tag, code, probe, control in FLUIDS[cid]["probes"]:
        if tag not in tags:
            continue
        count += 1
        problem = refusal_problem(
            request(provider, cid, probe), STATUS.get(code, "unsupported"), code
        )
        if problem:
            problems.append(f"{tag} {probe}: {problem}")
        answered = request(provider, cid, control)
        if answered.status != "ok":
            problems.append(f"{tag} control {control}: {answered.status} {answered.message}")
    return problems if count else [f"no {tags} probe in ref"]


def a28_problems(module: types.ModuleType, cids: Iterable[str] = tuple(TIER_A)) -> list[str]:
    """§16.9's recipe from the files' bytes, and §5.1's canonical fluid hash, for `cids`."""
    problems = []
    canonical = {"sort_keys": True, "separators": (",", ":"), "ensure_ascii": True}
    implementation = hashlib.sha256(
        json.dumps(
            {
                "module_sha256": hashlib.sha256(MODULE_PATH.read_bytes()).hexdigest(),
                "fluid_table_sha256": hashlib.sha256(
                    (MODULE_PATH.parent / "_coolprop_heos_fluids.py").read_bytes()
                ).hexdigest(),
                "coolprop_version": "8.0.0",
                "coolprop_gitrevision": "ae81610e7d23efc57f9d051c8e70a4d66e87537f",
            },
            **canonical,  # type: ignore[arg-type]
        ).encode()
    ).hexdigest()
    for cid in cids:
        described = module.CoolPropHeosProvider(cid).describe()
        data = hashlib.sha256(
            json.dumps(
                {
                    "coolprop_version": "8.0.0",
                    "fluid": ROWS[cid]["name"],
                    "fluid_data_sha256": FLUIDS[cid]["fluid_data_sha256"],
                },
                **canonical,  # type: ignore[arg-type]
            ).encode()
        ).hexdigest()
        if (described.implementation_sha256, described.data_sha256) != (implementation, data):
            problems.append(f"{cid}: identity does not follow §16.9")
        if module.fluid_data_sha256(ROWS[cid]["name"]) != FLUIDS[cid]["fluid_data_sha256"]:
            problems.append(f"{cid}: fluid_data_sha256 does not follow §5.1")
    return problems


#: Spec A27's allowed CoolProp names, and the forbidden ones it names.
GETTERS = tuple(
    f"{prefix}alpha{kind}{suffix}"
    for kind in ("0", "r")
    for prefix, suffix in (
        ("", ""),
        ("d", "_dDelta"),
        ("d2", "_dDelta2"),
        ("d", "_dTau"),
        ("d2", "_dTau2"),
        ("d2", "_dDelta_dTau"),
        ("d3", "_dDelta3"),
        ("d3", "_dDelta2_dTau"),
        ("d3", "_dDelta_dTau2"),
        ("d3", "_dTau3"),
    )
)
ALLOWED = {
    "AbstractState",
    "specify_phase",
    "iphase_gas",
    "update",
    "DmolarT_INPUTS",
    "get_fluid_param_string",
    "get_global_param_string",
    "__version__",
    *GETTERS,
}
FORBIDDEN = {
    "set_reference_state",
    "add_fluids_as_JSON",
    "PropsSI",
    "PhaseSI",
    "p",
    "hmolar",
    "smolar",
    "rhomolar",
    "cpmolar",
    "fugacity_coefficient",
    "T_critical",
    "rhomolar_critical",
    "melting_line",
    "first_partial_deriv",
}
#: The names the module binds CoolProp objects to.
COOLPROP_NAMES = {"coolprop", "library", "heos"}


def a27_problems(source: str) -> list[str]:
    tree = ast.parse(source)
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            names = [alias.name for alias in node.names] + [getattr(node, "module", "") or ""]
            if any(name.split(".")[0] == "CoolProp" for name in names):
                problems.append(f"line {node.lineno}: CoolProp imported eagerly")
        if isinstance(node, ast.Attribute):
            if node.attr in FORBIDDEN or node.attr.startswith("set_config"):
                problems.append(f"line {node.lineno}: forbidden name {node.attr}")
            owner = node.value
            if isinstance(owner, ast.Name) and owner.id in COOLPROP_NAMES:
                if node.attr not in ALLOWED:
                    problems.append(f"line {node.lineno}: {owner.id}.{node.attr} is not allowed")
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    jet = [f for f in functions if f.name == "_jet"]
    used = {n.attr for f in jet for n in ast.walk(f) if isinstance(n, ast.Attribute)}
    problems += [f"_jet does not call {name}" for name in GETTERS if name not in used]
    for function in functions:
        calls = [n for n in ast.walk(function) if isinstance(n, ast.Attribute)]
        if function.name != "_jet" and any(n.attr == "update" for n in calls):
            problems.append(f"{function.name} calls update outside _jet")
        if not any(n.attr == "AbstractState" for n in calls):
            continue
        phase = [
            n.lineno
            for n in ast.walk(function)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Attribute)
            and n.func.attr == "specify_phase"
            and any(isinstance(a, ast.Attribute) and a.attr == "iphase_gas" for a in n.args)
        ]
        first = min((n.lineno for n in calls if n.attr in ("_jet", "update")), default=math.inf)
        if not phase or min(phase) > first:
            problems.append(f"{function.name}: specify_phase(iphase_gas) is not before update")
    return problems


def a34_problems(provider: Provider, cid: str) -> list[str]:
    ref, described = FLUIDS[cid], provider.describe()
    problems = []
    if not described.uncertainty.startswith(f"verification: {ref['verification']}"):
        problems.append(f"{cid}: uncertainty {described.uncertainty!r}")
    carries = E_SENTENCE in described.numerical_limitations
    if carries != (ref["bound"] == "E"):
        problems.append(f"{cid}: bound {ref['bound']} and the E sentence present = {carries}")
    if ref["tier"] == "B" and described.uncertainty.startswith("verification: independent:"):
        problems.append(f"{cid}: a tier-B fluid reports independent verification")
    return problems


# -- A01, A02, A28, A33, A34: identity and the fluid list ------------------------------------------


@pytest.mark.parametrize("cid", TIER_A)
def test_a01_constants_are_refs_bitwise(cid: str) -> None:
    assert a01_problems(PROVIDERS[cid], cid) == []


@pytest.mark.parametrize("cid", TIER_A)
def test_a02_describe(cid: str) -> None:
    check_a02(PROVIDERS[cid], cid)


def check_a02(provider: Provider, cid: str) -> None:
    """A02: `describe()` as spec §3.2, with §16.8's strings (both tiers)."""
    described, fluid = provider.describe(), FLUIDS[cid]["constants"]
    assert described.provider_id == "coolprop-heos-v1"
    assert described.reference_convention == "COOLPROP-DEF-ref-v1"
    assert described.state_definition == "nTP-v1"
    assert described.components == (cid,)
    assert described.phases == ("LIQUID", "VAPOR")
    assert described.properties == (*six(cid), "Psat", "Tsat")
    assert described.flashes == ("TP",)
    assert described.derivative_order == {"T": 1, "P": 1, f"n_{cid}": 1}
    assert described.domain == {
        "T": (fluid["T_lo"], fluid["T_hi"]),
        "P": (fluid["P_lo"], fluid["P_hi"]),
    }
    assert described.thread_safety == "not_thread_safe"
    name, bibtex = ROWS[cid]["name"], ROWS[cid]["bibtex_eos"]
    assert described.data_provenance == (
        f"CoolProp 8.0.0 (MIT), fluid {name}, not redistributed; {bibtex}"
    )
    assert described.uncertainty == (
        f"verification: {FLUIDS[cid]['verification']}; EOS {bibtex} as evaluated by CoolProp "
        "8.0.0; the EOS's own uncertainty is not re-validated"
    )


#: Run in a subprocess with `sys.modules["CoolProp"] = None` (A02, A26(a), A28).
ABSENT_SCRIPT = """
import json, sys
sys.modules["CoolProp"] = None
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import FlashRequest, PropertyRequest, StreamState
from openflowsheet.thermo import coolprop_heos as m
context = EvaluationContext(model_version="s07-absent", constants_sha256="0" * 64)
out = {}
for cid, t, p in json.loads(sys.argv[1]):
    provider = m.CoolPropHeosProvider(cid)
    state = StreamState(n=(1.0,), temperature=t, pressure=p)
    names = ["h", "s", "v", "Z", "cp", "lnphi_" + cid, "Psat", "Tsat"]
    messages = [
        provider.evaluate_phase(PropertyRequest(state, "VAPOR", (x,), ()), context).message
        for x in names
    ]
    messages.append(provider.flash(FlashRequest(state, "TP", ()), context).message)
    try:
        m.helmholtz_jet(cid, t, 1.0)
        jet = "returned"
    except m.CoolPropUnavailable as error:
        jet = error.code
    out[cid] = {"describe": repr(provider.describe()), "messages": messages, "jet": jet}
print(json.dumps(out))
"""


def run_script(script: str, *arguments: Any) -> Any:
    completed = subprocess.run(
        [sys.executable, "-c", script, *(json.dumps(a) for a in arguments)],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
        timeout=600,
    )
    assert completed.returncode == 0, completed.stderr[-4000:]
    return json.loads(completed.stdout.splitlines()[-1])


@pytest.fixture(scope="module")
def absent() -> dict[str, Any]:
    states = [[cid, *tp(cid, "V_sup")[:2]] for cid in TIER_A]
    result: dict[str, Any] = run_script(ABSENT_SCRIPT, states)
    return result


def test_a02_a28_describe_answers_without_coolprop_with_the_same_identity(
    absent: dict[str, Any],
) -> None:
    for cid in TIER_A:
        assert absent[cid]["describe"] == repr(PROVIDERS[cid].describe()), cid


@needs_coolprop
def test_a28_identity_recipe() -> None:
    assert a28_problems(cph) == []


def test_a33_the_fluid_list() -> None:
    admitted = Provider.admitted()
    assert [entry["id"] for entry in admitted] == [row["id"] for row in table.FLUIDS]
    assert {entry["id"]: entry for entry in admitted} == {
        cid: {
            "id": cid,
            "name": ref["name"],
            "cas": ref["cas"],
            "tier": ref["tier"],
            "bound": ref["bound"],
        }
        for cid, ref in FLUIDS.items()
    }
    for entry in admitted:
        Provider(entry["id"])  # constructs without CoolProp
    assert Provider.excluded() == REF["excluded"]
    for name, reason in REF["excluded"].items():
        for spelling in {name, name.replace("(", "_").replace(")", "")}:
            with pytest.raises(ValueError, match="excluded") as raised:
                Provider(spelling)
            assert reason in str(raised.value)
    for unknown in ("Nitrogen", "XYZ", "n2"):
        with pytest.raises(ValueError, match="not a component id"):
            Provider(unknown)


def test_a33c_no_fluid_literal_in_the_algorithm_module() -> None:
    spellings = set(FLUIDS) | {ref["name"] for ref in FLUIDS.values()}
    spellings |= set(REF["excluded"]) | {
        name.replace("(", "_").replace(")", "") for name in REF["excluded"]
    }
    tree = ast.parse(MODULE_PATH.read_text("utf-8"))
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    assert literals & spellings == set()


@pytest.mark.parametrize("cid", TIER_A)
def test_a34_tier_and_bound_are_reported(cid: str) -> None:
    assert a34_problems(Provider(cid), cid) == []


# -- A03, A04, A24: the jet ------------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a03_jet_orders_up_to_two(cid: str) -> None:
    keys = set(FLUIDS[cid]["phi_states"])
    assert {"phi_gas", "phi_liq", "phi_dilute"} <= keys
    assert ("delta_one" in keys) == (cid in ("H2O", "CO2"))  # spec §7: H2O and CO2 only
    assert a03_problems(cph, cid, LOW_ORDER, 1e-12) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a04_third_partials(cid: str) -> None:
    assert a03_problems(cph, cid, THIRD_ORDER, 1e-11) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a24_ideal_gas_cp_against_s04(cid: str) -> None:
    index = pr_lib.COMPONENTS.index(cid)
    m = FLUIDS[cid]["constants"]["M"]
    r, t_red = FLUIDS[cid]["constants"]["R"], FLUIDS[cid]["constants"]["T_red"]
    for t in (300.0, 600.0):
        ideal, _ = cph.helmholtz_jet(cid, t, 1.0)
        cp_ig = r * (1.0 - (t_red / t) ** 2 * ideal.tt)
        library = pr_lib.cp_ig(t, index)
        assert abs(cp_ig / library - 1.0) <= 0.02, (t, cp_ig, library)
        assert abs((cp_ig / m) / library - 1.0) > 10 * 0.02  # control: J/kg for J/mol fails
        # Not numbered: the generator's 50-digit value of the same expression.
        expected = FLUIDS[cid]["s04_ig"][repr(t)]
        assert abs(cp_ig - expected) <= 1e-12 * abs(expected), (t, cp_ig, expected)


# -- A05-A07: TP states ----------------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a05_values(cid: str) -> None:
    assert a05_problems(PROVIDERS[cid], cid) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a06_t_and_p_derivatives(cid: str) -> None:
    assert a06_problems(PROVIDERS[cid], cid) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a07_n_derivatives_are_exactly_zero(cid: str) -> None:
    assert a07_problems(PROVIDERS[cid], cid) == []


# -- A08-A12: saturation ---------------------------------------------------------------------------


def both_phases_at_psat(
    provider: Provider, t: float
) -> tuple[PropertyResult, PropertyResult, PropertyResult]:
    sat = psat(provider, t)
    assert sat.status == "ok", sat.message
    p = sat.values["Psat"]
    return sat, ev(provider, t, p, "LIQUID"), ev(provider, t, p, "VAPOR")


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
@pytest.mark.parametrize("key", ["sat_lo", "sat_mid", "sat_hi"])
def test_a08_psat_and_its_slope(cid: str, key: str) -> None:
    entry = FLUIDS[cid]["saturation"][key]
    result = psat(PROVIDERS[cid], entry["T"])
    assert result.status == "ok", result.message
    assert abs(result.values["Psat"] / entry["Psat"] - 1.0) <= 2e-9
    assert abs(result.derivatives["Psat"]["T"] / entry["dPsat_dT"] - 1.0) <= 1e-8
    assert result.derivatives["Psat"]["P"] == 0.0
    assert result.derivatives["Psat"][f"n_{cid}"] == 0.0


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a09_tsat_and_its_slope(cid: str) -> None:
    entry = FLUIDS[cid]["tsat"]["tsat_mid"]
    result = ev(PROVIDERS[cid], band_t(cid), entry["P"], "VAPOR", ("Tsat",))
    assert result.status == "ok", result.message
    assert abs(result.values["Tsat"] / entry["Tsat"] - 1.0) <= 1e-9
    assert abs(result.derivatives["Tsat"]["P"] / entry["dTsat_dP"] - 1.0) <= 1e-8
    assert result.derivatives["Tsat"]["T"] == 0.0
    assert result.derivatives["Tsat"][f"n_{cid}"] == 0.0


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
@pytest.mark.parametrize("key", ["sat_lo", "sat_mid", "sat_hi"])
def saturated_phases(
    provider: Provider, t: float
) -> tuple[PropertyResult, dict[str, float], dict[str, float]]:
    """The provider's Psat at T, and its two saturated phases' values at (T, Psat).

    DECISION (WO-S07-2a, docs/S07_DECISIONS.md B-18): where Psat(T) < P_lo (C2H6 and C3H8 at
    `sat_lo`: 32.5 Pa and 4.9e-3 Pa) `evaluate_phase` refuses (T, Psat) `out_of_domain` (spec §6.5
    row 5), so A10/A11 read the two phases from the provider's own saturation state through the
    same property path `evaluate_phase` uses (`_saturation`, `_at` at the root pressure). Inside
    the box the public path is used, as S05 A10/A11. Pending a design ruling.
    """
    sat = psat(provider, t)
    assert sat.status == "ok", sat.message
    p = sat.values["Psat"]
    if p >= provider._fluid.p_lo:
        liquid, vapour = ev(provider, t, p, "LIQUID"), ev(provider, t, p, "VAPOR")
        assert liquid.status == vapour.status == "ok", (liquid.message, vapour.message)
        return sat, liquid.values, vapour.values
    root = provider._saturation(t)
    assert root is not None and root.pressure == p
    phases = (provider._at(t, rho, p) for rho in (root.rho_l, root.rho_v))
    liquid_values, vapour_values = ({x: v[0] for x, v in phase.items()} for phase in phases)
    return sat, liquid_values, vapour_values


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
@pytest.mark.parametrize("key", ["sat_lo", "sat_mid", "sat_hi"])
def test_a10_maxwell_on_the_providers_own_psat(cid: str, key: str) -> None:
    entry = FLUIDS[cid]["saturation"][key]
    _, liquid, vapour = saturated_phases(PROVIDERS[cid], entry["T"])
    lnphi = f"lnphi_{cid}"
    assert abs(liquid[lnphi] - vapour[lnphi]) <= 1e-8
    bound = 1e-6 if key == "sat_hi" else 1e-9
    assert abs((vapour["h"] - liquid["h"]) / entry["dh_vap"] - 1.0) <= bound


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
@pytest.mark.parametrize("key", ["sat_lo", "sat_mid", "sat_hi"])
def test_a11_clausius_clapeyron_on_the_providers_answers(cid: str, key: str) -> None:
    sat, liquid, vapour = saturated_phases(PROVIDERS[cid], FLUIDS[cid]["saturation"][key]["T"])
    ratio = (vapour["s"] - liquid["s"]) / (vapour["v"] - liquid["v"])
    bound = 1e-6 if key == "sat_hi" else 1e-8
    assert abs(sat.derivatives["Psat"]["T"] / ratio - 1.0) <= bound


def internal_energy_and_entropy(provider: Provider, t: float) -> tuple[float, float]:
    sat, liquid, _ = both_phases_at_psat(provider, t)
    return liquid.values["h"] - sat.values["Psat"] * liquid.values["v"], liquid.values["s"]


@needs_coolprop
def test_a12_the_datum_h2o() -> None:
    u, s = internal_energy_and_entropy(PROVIDERS["H2O"], 273.16)
    assert abs(u) <= 1e-6 and abs(s) <= 1e-8, (u, s)
    assert abs(float(S05["datum"]["u_l_triple"])) <= 1e-6
    u450, s450 = internal_energy_and_entropy(PROVIDERS["H2O"], 450.0)
    assert abs(u450) > 1000.0 and abs(s450) > 10.0  # control


# -- A13-A16, A18, A19, A21: the band, refusal probes and controls ---------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a13_band_probes(cid: str) -> None:
    assert a13_problems(PROVIDERS[cid], cid) == []
    assert probe_problems(PROVIDERS[cid], cid, ("A13",)) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
@pytest.mark.parametrize("tag", ["A14", "A15", "A16", "A18", "A21"])
def test_refusal_probes(cid: str, tag: str) -> None:
    assert probe_problems(PROVIDERS[cid], cid, (tag,)) == []


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a19_saturation_only_skips_the_phase_check(cid: str) -> None:
    t, p, _ = tp(cid, "V_sub")
    only = ev(PROVIDERS[cid], t, p, "LIQUID", ("Psat",))
    assert only.status == "ok" and only.phase_signature == "LIQUID", only.message
    refused(ev(PROVIDERS[cid], t, p, "LIQUID", ("Psat", "h")), "unsupported", "phase_not_stable")


def _starved(provider_id: str, call: Callable[[Provider], Result]) -> Result:
    """`call` on a fresh instance (cold saturation cache) with no Newton iteration allowed."""
    provider = Provider(provider_id)
    provider._guard()
    saved = cph.MAX_ITERATIONS
    try:
        cph.MAX_ITERATIONS = 0  # type: ignore[misc]
        return call(provider)
    finally:
        cph.MAX_ITERATIONS = saved  # type: ignore[misc]


class _Raising:
    """An `AbstractState` stand-in whose `update` raises (spec §18.1, row 11)."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def update(self, *arguments: Any) -> None:
        raise ValueError("injected CoolProp failure")

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


@needs_coolprop
def test_a21_rows_10_and_11_by_injection() -> None:
    """Spec §18.1: N2, each forced refusal with its unforced control."""
    t, p, phase = tp("N2", "V_sup")
    sat_t = FLUIDS["N2"]["saturation"]["sat_mid"]["T"]

    def density(provider: Provider) -> Result:
        return ev(provider, t, p, phase, ("h",))

    def saturation(provider: Provider) -> Result:
        return psat(provider, sat_t)

    refused(_starved("N2", density), "not_converged", "density_not_converged")
    assert density(Provider("N2")).status == "ok"
    refused(_starved("N2", saturation), "not_converged", "saturation_not_converged")
    assert saturation(Provider("N2")).status == "ok"
    broken = Provider("N2")
    assert broken._guard() is None
    broken._state = _Raising(broken._state)
    refused(density(broken), "error", "coolprop_evaluation_failed")
    refused(flash(broken, sat_t, 1.0e5), "error", "coolprop_evaluation_failed")
    assert density(Provider("N2")).status == "ok"


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a21_contract_refusals_and_construction(cid: str) -> None:
    provider = PROVIDERS[cid]
    t, p, phase = tp(cid, "V_sup")
    other = "n_H2O" if cid != "H2O" else "n_N2"
    refused(
        ev(provider, t, p, phase, derivatives=(other,)),
        "unsupported",
        "undeclared_derivative_input",
    )
    refused(ev(provider, t, p, phase, ("g",)), "unsupported", "unknown_property")
    refused(ev(provider, t, p, phase, n=(1.0, 0.0)), "error", "state_length")
    refused(ev(provider, t, p, phase, n=(0.0,)), "unsupported", "dormant_state")
    assert ev(provider, t, p, phase).status == "ok"
    with pytest.raises(ValueError):
        Provider(cid.lower() + "_x")


# -- A17: value/derivative consistency (S05 §6.3) --------------------------------------------------

FD_TOL = 1e-10
FD_STEP = 1e-6
FD_STEP_NC = 1e-7


def fd_scale(x: str, t: float, r: float) -> float:
    if x.startswith("lnphi_"):
        return 1.0
    return {"h": r * t, "s": r, "cp": r, "Z": 1.0, "v": 0.0}[x]


def fd_stencil(provider: Provider, t: float, p: float, wrt: str, kind: str) -> tuple[float, float]:
    """S05 §14 (R-597): the step and the side of the stencil (0 central, ±1 inward at a box edge);
    `kind` is "nc", "band" or "tp"."""
    fluid = provider._fluid
    x, low, high = (t, fluid.t_lo, fluid.t_hi) if wrt == "T" else (p, fluid.p_lo, fluid.p_hi)
    side = 1.0 if x == low else -1.0 if x == high else 0.0
    if kind == "band":
        if wrt == "P":
            return fluid.eps_sigma / 4.0 * p, side
        sat = psat(provider, t)
        assert sat.status == "ok", sat.message
        slope = sat.derivatives["Psat"]["T"] / sat.values["Psat"]
        return fluid.eps_sigma / 4.0 / abs(slope), side
    return (FD_STEP_NC if kind == "nc" else FD_STEP) * x, side


def fd_ratios(
    provider: Provider, cid: str, t: float, p: float, phase: Phase, wrt: str, kind: str
) -> dict[str, float]:
    h, side = fd_stencil(provider, t, p, wrt, kind)
    r = provider._fluid.r

    def at(k: float) -> PropertyResult:
        return (
            ev(provider, t + k * h, p, phase) if wrt == "T" else ev(provider, t, p + k * h, phase)
        )

    centre = ev(provider, t, p, phase)
    first, second = (at(1.0), at(-1.0)) if side == 0.0 else (at(side), at(2.0 * side))
    for result in (centre, first, second):
        if result.status != "ok":
            raise AssertionError(f"a stencil point is refused: {result.message}")
    ratios = {}
    for x in six(cid):
        f0, f1, f2 = centre.values[x], first.values[x], second.values[x]
        slope = 2.0 * h * centre.derivatives[x][wrt]
        if side == 0.0:
            miss, scale = abs(f1 - f2 - slope), max(abs(f1), abs(f2), fd_scale(x, t, r))
        else:
            miss = abs(side * (-3.0 * f0 + 4.0 * f1 - f2) - slope)
            scale = max(abs(f0), abs(f1), abs(f2), fd_scale(x, t, r))
        ratios[x] = miss / scale
    return ratios


def fd_cases(cid: str) -> list[tuple[float, float, Phase, str, str, str]]:
    """Every TP state and every answered band phase, in T and in P: none dropped (R-597)."""
    cases = []
    for name in FLUIDS[cid]["tp_states"]:
        t, p, phase = tp(cid, name)
        for wrt in ("T", "P"):
            cases.append((t, p, phase, wrt, "nc" if name in NC else "tp", f"{name}-{wrt}"))
    for key, probe in FLUIDS[cid]["band"]["probes"].items():
        for phase in probe["answered"]:
            for wrt in ("T", "P"):
                cases.append((band_t(cid), float(probe["P"]), phase, wrt, "band", f"band{key}"))
    return cases


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a17_finite_differences(cid: str) -> None:
    worst: dict[str, float] = {}
    for t, p, phase, wrt, kind, label in fd_cases(cid):
        ratios = fd_ratios(PROVIDERS[cid], cid, t, p, phase, wrt, kind)
        worst[f"{label}-{phase}-{wrt}"] = max(ratios.values())
    assert max(worst.values()) <= FD_TOL, {k: v for k, v in worst.items() if v > FD_TOL}


# -- A20: flash ------------------------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a20_flash(cid: str) -> None:
    provider = PROVIDERS[cid]
    for name in FLUIDS[cid]["tp_states"]:
        t, p, phase = tp(cid, name)
        result = flash(provider, t, p)
        assert result.status == "ok" and result.phase_signature == phase, (name, result.message)
        state = StreamState(n=(1.0,), temperature=t, pressure=p)
        empty = StreamState(n=(0.0,), temperature=t, pressure=p)
        assert result.vapor_fraction == (1.0 if phase == "VAPOR" else 0.0)
        expected = (state, empty) if phase == "VAPOR" else (empty, state)
        assert (result.vapor, result.liquid) == expected
        assert dict(result.k_values) == {}
    probes = FLUIDS[cid]["band"]["probes"]
    refused(flash(provider, band_t(cid), probes["0.5"]["P"]), "unsupported", "tp_flash_degenerate")
    control = flash(provider, band_t(cid), probes["-2"]["P"])
    assert control.status == "ok" and control.vapor_fraction == 1.0
    t, p, _ = tp(cid, "L_sub")
    dormant = flash(provider, t, p, n=(0.0,))
    zero = StreamState(n=(0.0,), temperature=t, pressure=p)
    assert (dormant.status, dormant.phase_signature, dormant.vapor_fraction) == (
        "ok",
        "ZERO_FLOW",
        None,
    )
    assert (dormant.vapor, dormant.liquid) == (zero, zero)
    refused(flash(provider, t, p, spec="PH"), "unsupported", "unsupported_specification")
    refused(flash(provider, t, p, der=("T",)), "unsupported", "flash_derivatives_unsupported")
    refused(flash(provider, t, p, n=(1.0, 0.0)), "error", "state_length")
    assert flash(provider, t, p).status == "ok"


# -- A22: the robustness grid ----------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a22_robustness_grid(cid: str) -> None:
    provider, fluid = PROVIDERS[cid], PROVIDERS[cid]._fluid
    temperatures = [fluid.t_lo + (fluid.t_hi - fluid.t_lo) * i / 23 for i in range(24)]
    temperatures[-1] = fluid.t_hi
    pressures = [10.0**k for k in range(2, 9) if 10.0**k <= fluid.p_hi]
    pressures += [fluid.p_hi] if fluid.p_hi not in pressures else []
    problems, answered = [], 0
    for t in temperatures:
        if t <= fluid.t_sigma_max:
            sat = psat(provider, t)
            problems += [f"Psat at {t}: {sat.message}"] if sat.status != "ok" else []
        for p in pressures:
            for phase in ("LIQUID", "VAPOR"):
                result = ev(provider, t, p, phase)
                if result.status != "ok":
                    code = result.message.split(":")[0]
                    if code not in ("phase_not_stable", "near_critical"):
                        problems.append(f"{phase} at {t}, {p}: {result.message}")
                    continue
                answered += 1
                if not result.derivatives["v"]["P"] < 0.0 or not result.values["cp"] > 0.0:
                    problems.append(f"{phase} at {t}, {p}: dv/dP or cp has the wrong sign")
    assert problems == []
    assert answered >= len(temperatures) * len(pressures)  # every (T, P) answers some phase


# -- A23: water against S05 ------------------------------------------------------------------------


@needs_coolprop
def test_a23_water_against_s05() -> None:
    provider, problems = PROVIDERS["H2O"], []
    names = six("H2O")
    r = FLUIDS["H2O"]["constants"]["R"]
    for name, state in S05["tp_states"].items():
        t, p = float(state["T"]), float(state["P"])
        if t > 646.9:
            continue
        result = ev(provider, t, p, state["phase"])
        assert result.status == "ok", (name, result.message)
        for x in names:
            expected = float(state[x])
            if not abs(result.values[x] - expected) <= value_bound(name, x, t, expected, r):
                problems.append(f"{name} {x}")
            for wrt in ("T", "P"):
                slope = float(state[f"d{x}_d{wrt}"])
                if not abs(result.derivatives[x][wrt] - slope) <= 1e-8 * abs(slope):
                    problems.append(f"{name} d{x}/d{wrt}")
    for key, entry in S05["saturation"].items():
        t = float(entry["T"])
        if t > 646.9:
            continue
        sat, liquid, vapour = both_phases_at_psat(provider, t)
        if abs(sat.values["Psat"] / float(entry["Psat"]) - 1.0) > 2e-9:
            problems.append(f"sat {key} Psat")
        if abs(sat.derivatives["Psat"]["T"] / float(entry["dPsat_dT"]) - 1.0) > 1e-8:
            problems.append(f"sat {key} dPsat/dT")
        latent = float(entry["h_v"]) - float(entry["h_l"])
        if abs((vapour.values["h"] - liquid.values["h"]) / latent - 1.0) > 1e-9:
            problems.append(f"sat {key} h_v - h_l")
        if abs(liquid.values["lnphi_H2O"] - vapour.values["lnphi_H2O"]) > 1e-8:
            problems.append(f"sat {key} Maxwell")
    t = float(S05["band"]["T"])
    for key, probe in S05["band"]["probes"].items():
        for phase in probe["answered"]:
            result = ev(provider, t, float(probe["P"]), phase)
            assert result.status == "ok", (key, phase, result.message)
            for x in names:
                expected = float(probe[phase][x])
                if not abs(result.values[x] - expected) <= value_bound(key, x, t, expected, r):
                    problems.append(f"band {key} {phase} {x}")
    assert problems == []


# -- A25: determinism ------------------------------------------------------------------------------


@needs_coolprop
@pytest.mark.parametrize("cid", TIER_A)
def test_a25_determinism_and_identity(cid: str) -> None:
    provider, fluid = PROVIDERS[cid], PROVIDERS[cid]._fluid
    t, p, phase = tp(cid, "L_sub")
    calls: list[Callable[[], Result]] = [
        lambda: ev(provider, t, p, phase),
        lambda: ev(provider, *tp(cid, "NC_V")),
        lambda: ev(provider, band_t(cid), FLUIDS[cid]["band"]["probes"]["0.5"]["P"], "LIQUID"),
        lambda: psat(provider, band_t(cid)),
        lambda: ev(provider, t, FLUIDS[cid]["tsat"]["tsat_mid"]["P"], "VAPOR", ("Tsat",)),
        lambda: ev(provider, sum(fluid.nc_t) / 2, sum(fluid.nc_p) / 2, "VAPOR"),
        lambda: ev(provider, t, p, phase, ("g",)),
        lambda: ev(provider, fluid.t_lo * (1 - 1e-6), p, phase),
        lambda: flash(provider, t, p),
        lambda: flash(provider, t, p, spec="PH"),
        lambda: flash(provider, band_t(cid), FLUIDS[cid]["band"]["probes"]["0.5"]["P"]),
    ]
    for call in calls:
        first, second = call(), call()
        assert repr(first) == repr(second)
        assert first.provider_id == "coolprop-heos-v1"
        assert first.reference_convention == "COOLPROP-DEF-ref-v1"
        assert first.achieved_accuracy == "exact-double"
        if isinstance(first, PropertyResult):
            assert all(math.isfinite(value) for value in first.values.values())


# -- A26: the guard --------------------------------------------------------------------------------


def test_a26a_coolprop_unimportable(absent: dict[str, Any]) -> None:
    for cid in TIER_A:
        messages = absent[cid]["messages"]
        assert len(messages) == 9
        assert all(message.startswith("coolprop_unavailable:") for message in messages), messages
        assert absent[cid]["jet"] == "coolprop_unavailable"


@needs_coolprop
def test_a26b_version_and_data_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    coolprop = importlib.import_module("CoolProp")
    library = importlib.import_module("CoolProp.CoolProp")

    t, p, phase = tp("N2", "V_sup")
    monkeypatch.setattr(coolprop, "__version__", "7.0.0")
    refused(ev(Provider("N2"), t, p, phase), "unsupported", "coolprop_version_mismatch")
    monkeypatch.setattr(cph, "_JET_PROVIDERS", {})
    with pytest.raises(cph.CoolPropUnavailable) as raised:
        cph.helmholtz_jet("N2", t, 1.0)
    assert raised.value.code == "coolprop_version_mismatch"
    monkeypatch.undo()
    original = library.get_fluid_param_string

    def edited(name: str, key: str) -> str:
        text: str = original(name, key)
        return text.replace('"Nitrogen"', '"Nitrogen "', 1) if key == "JSON" else text

    monkeypatch.setattr(library, "get_fluid_param_string", edited)
    refused(ev(Provider("N2"), t, p, phase), "unsupported", "coolprop_data_mismatch")
    refused(flash(Provider("N2"), t, p), "unsupported", "coolprop_data_mismatch")
    monkeypatch.undo()
    assert ev(Provider("N2"), t, p, phase).status == "ok"  # control


#: Run in a subprocess (A26(c), Q-3): a reference-state change before and after the first
#: evaluation; argv[2] is an optional source mutation (A32 m7).
MUTATED_SCRIPT = """
import json, sys, types
from pathlib import Path
from CoolProp import CoolProp as cp
from openflowsheet.compiled import EvaluationContext
from openflowsheet.thermo import PropertyRequest, StreamState
from openflowsheet.thermo import coolprop_heos as m
mutation = json.loads(sys.argv[2])
if mutation:
    source = Path(m.__file__).read_text("utf-8")
    assert source.count(mutation[0]) == 1
    module = types.ModuleType("openflowsheet.thermo._s07_mutant")
    module.__file__ = m.__file__
    sys.modules[module.__name__] = module
    exec(compile(source.replace(*mutation), m.__file__, "exec"), module.__dict__)
    m = module
context = EvaluationContext(model_version="s07-mutated", constants_sha256="0" * 64)
def alpha0(name):
    heos = cp.AbstractState("HEOS", name)
    heos.update(cp.DmolarT_INPUTS, 100.0, 400.0)
    return heos.alpha0()
def perturb(name):
    # The first of NBP, ASHRAE, IIR that moves a fresh state's alpha0 by O(1); for a fluid whose
    # named states all coincide with DEF (CH4, H2: NBP), an explicit offset.
    default = alpha0(name)
    for used in ("NBP", "ASHRAE", "IIR"):
        try:
            cp.set_reference_state(name, used)
        except ValueError:
            continue
        if abs(alpha0(name) - default) > 1e-3:
            return used
        cp.set_reference_state(name, "DEF")
    cp.set_reference_state(name, 300.0, 100.0, 1000.0, 10.0)
    return "explicit"
out = {}
for cid, name, t, p, phase in json.loads(sys.argv[1]):
    names = ("h", "s", "cp", "lnphi_" + cid)
    request = PropertyRequest(StreamState(n=(1.0,), temperature=t, pressure=p), phase, names, ())
    def run(provider):
        result = provider.evaluate_phase(request, context)
        return [result.message] + [v.hex() for v in result.values.values()]
    used = perturb(name)
    before = run(m.CoolPropHeosProvider(cid))
    cp.set_reference_state(name, "DEF")
    kept = m.CoolPropHeosProvider(cid)
    first = run(kept)
    perturb(name)
    second = run(kept)
    cp.set_reference_state(name, "DEF")
    out[cid] = {"reference": used, "before": before, "first": first, "second": second}
print(json.dumps(out))
"""


def a26c_problems(mutation: list[str] | None) -> list[str]:
    states = [[cid, ROWS[cid]["name"], *tp(cid, "V_sup")] for cid in TIER_A]
    out = run_script(MUTATED_SCRIPT, states, mutation)
    problems = []
    for cid in TIER_A:
        entry = out[cid]
        if not entry["before"][0].startswith("coolprop_state_mutated:"):
            problems.append(f"{cid} ({entry['reference']}): before is {entry['before'][0]!r}")
        if entry["first"][0] != "" or entry["second"] != entry["first"]:
            problems.append(f"{cid}: values moved after a later reference-state change")
    return problems


@needs_coolprop
def test_a26c_reference_state_before_and_after_the_first_evaluation() -> None:
    assert a26c_problems(None) == []


# -- A27: Helmholtz evaluator only -----------------------------------------------------------------


def test_a27_only_the_helmholtz_calls() -> None:
    assert a27_problems(MODULE_PATH.read_text("utf-8")) == []


# -- A32: the mutation battery ---------------------------------------------------------------------


def mutant(old: str, new: str) -> types.ModuleType:
    """The provider module with one source edit, loaded under a private name."""
    source = MODULE_PATH.read_text("utf-8")
    assert source.count(old) == 1, old
    module = types.ModuleType("openflowsheet.thermo._s07_mutant")
    module.__file__ = str(MODULE_PATH)
    sys.modules[module.__name__] = module
    try:
        exec(compile(source.replace(old, new), str(MODULE_PATH), "exec"), module.__dict__)
    finally:
        del sys.modules[module.__name__]
    return module


def with_fluid(cid: str, **changes: Any) -> Provider:
    provider = Provider(cid)
    provider._fluid = dataclasses.replace(provider._fluid, **changes)
    return provider


M1 = (
    "                heos.d2alphar_dTau2(),\n                heos.d2alphar_dDelta_dTau(),\n",
    "                heos.d2alphar_dDelta_dTau(),\n                heos.d2alphar_dTau2(),\n",
)
M2 = ("        if temperature >= fluid.t_c:\n", "        if temperature >= fluid.t_red:\n")
M5 = (
    "                    for wanted in request.derivatives\n",
    "                    for wanted in request.derivatives\n"
    "                    if wanted in slot\n",
)
M6 = ("            heos.specify_phase(library.iphase_gas)\n", "")
M7 = (
    "            if not abs(value - expected) <= CANARY_TOLERANCE * max(abs(expected), 1.0):\n",
    "            if False:\n",
)
M8 = (
    "    return _sha256(_canonical(_fluid_json(library, name)))\n",
    '    return _sha256(library.get_fluid_param_string(name, "JSON"))\n',
)


@needs_coolprop
def test_a32_mutations_fail_their_assertions() -> None:
    m1 = mutant(*M1)
    assert guarded(lambda: a03_problems(m1, "N2", LOW_ORDER, 1e-12)) != []
    m1_n2 = m1.CoolPropHeosProvider("N2")
    assert guarded(lambda: a05_problems(m1_n2, "N2", ("cp",))) != []
    m2_o2 = mutant(*M2).CoolPropHeosProvider("O2")
    assert guarded(lambda: probe_problems(m2_o2, "O2", ("A15",))) != []
    assert guarded(lambda: a05_problems(with_fluid("N2", r=8.314462618), "N2")) != []  # m3
    assert guarded(lambda: a13_problems(with_fluid("N2", eps_sigma=0.0), "N2")) != []  # m4
    m5_n2 = mutant(*M5).CoolPropHeosProvider("N2")
    assert guarded(lambda: a07_problems(m5_n2, "N2")) != []
    source = MODULE_PATH.read_text("utf-8")
    assert a27_problems(source.replace(*M6)) != []  # m6
    assert guarded(lambda: a28_problems(mutant(*M8))) != []  # m8


@needs_coolprop
def test_a32_m7_skipping_g4_fails_a26c() -> None:
    assert a26c_problems(list(M7)) != []


@needs_coolprop
def test_a32_m9_to_m11_table_mutations() -> None:
    # m9: R1234ze_E served from R1234ze_Z's row.
    off = Provider("R1234ze_E")
    off._fluid = cph._Fluid.of(ROWS["R1234ze_Z"])
    assert a01_problems(off, "R1234ze_E") != []
    assert guarded(lambda: a05_problems(off, "R1234ze_E")) != []
    # m10: an E fluid's T_lo edited to its triple point.
    cid = next(row["id"] for row in table.FLUIDS if row["bound"] == "E")
    fluid = Provider(cid)._fluid
    triple = fluid.t_lo / (1.0 + 1e-8 * fluid.p_hi)
    edited = with_fluid(cid, t_lo=triple)
    assert a01_problems(edited, cid) != []
    below = next(
        probe
        for tag, code, probe, _ in FLUIDS[cid]["probes"]
        if tag == "A16" and probe[0] == "evaluate_phase" and probe[1] < fluid.t_lo
    )
    assert request(Provider(cid), cid, below).status == "out_of_domain"
    assert request(edited, cid, below).status == "ok"
    # m11: a tier-B fluid reports S04 verification.
    tier_b = next(row["id"] for row in table.FLUIDS if row["tier"] == "B")
    assert a34_problems(with_fluid(tier_b, verification="independent:S04-ig"), tier_b) != []
