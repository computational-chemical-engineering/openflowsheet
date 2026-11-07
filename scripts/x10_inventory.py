"""X10 inventory: which unit model × property basis pairs the revision path refuses today.

ADR 0056 row 9 (register R-925): "first a measured inventory of which unit × basis pairs refuse
today (some may be lifted by S10-C and S11)". A measurement, not a judgement of what should be
built; that is "X10 gaps" (0.6, on F6).

The axes are the code's: every model of `revision_binding.MODEL_BUILDERS` (the models the
revision path binds, `set(MODEL_BASES) == set(MODEL_BUILDERS)`) against every provider of
`revision_binding.SELECTABLE_BASES` (the bases a `record_source` selects). The 123 CoolProp bases
share one provider and `MODEL_BASES` keys on the provider id only, so one fluid stands for them
(`COOLPROP_FLUID`; docs/X10_DECISIONS.md D-1). The library-only models (`_LIBRARY_ONLY_HINTS`) and
the scanned providers no `record_source` selects are enumerated beside the matrix.

Each pair is probed through the binder a user's revision goes through (`bind_revision_flowsheet`,
then `select_route`), and a bound `revision_eo` pair is solved once (`solve_route`, the default
policy):

- a *native* probe is a registered corpus revision on that basis that holds the model (T07's G8
  corpus, M02's C1 corpus, the S11 and T08 benchmark revisions), smallest first, at most
  `MAX_TRIES` until one is VERIFIED;
- otherwise a *rebased* probe: the model's smallest registered revision moved onto the basis
  (component set and feed flows; the routing models swapped for the basis's own; the model under
  test first, so a refusal names it), with the feed state and outlet pressures of `CONSTRUCTED`
  where the pair is admitted and a solve is wanted (D-2).

Nothing in the production code is changed or relaxed. A refusal is recorded with its typed kind,
code and hint exactly as the binder returns them.

The CoolProp provider needs the optional `coolprop` extra. Its column is measured in each
environment separately and kept under `coolprop_extra_absent` / `coolprop_extra_present` (D-3);
`--record` re-measures the current environment's and keeps the other's, `--check` compares the
current environment's and every other pair.

Usage:
    PYTHONPATH=src .venv/bin/python scripts/x10_inventory.py --record
    PYTHONPATH=src .venv/bin/python scripts/x10_inventory.py --check
    PYTHONPATH=src .venv/bin/python scripts/x10_inventory.py --check --pairs syn001.liquid_pump
"""

from __future__ import annotations

import os

# Before numpy is imported: the probes' solves single-threaded, as the corpus runs are.
for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")

import argparse  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import importlib.util  # noqa: E402
import json  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from collections.abc import Callable, Mapping, Sequence  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Final  # noqa: E402

ROOT: Final = Path(__file__).resolve().parent.parent
for _entry in (ROOT / "tests", ROOT / "src"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

INVENTORY: Final = ROOT / "benchmarks" / "x10" / "inventory.json"
TABLE: Final = ROOT / "docs" / "X10-inventory.md"
SCHEMA: Final = "x10-inventory-v1"

#: D-1: the CoolProp fluid that stands for the provider's 123 bases (TH-C2's refrigerant).
COOLPROP_FLUID: Final = "R134a"
#: Native revisions tried per pair, smallest first, until one is VERIFIED.
MAX_TRIES: Final = 3
ENV_ABSENT: Final = "coolprop_extra_absent"
ENV_PRESENT: Final = "coolprop_extra_present"
ENV_ANY: Final = "any"
#: The revision a library-only model is bound in, standing in for its heater.
LIBRARY_ONLY_DONOR: Final = "g8:SYN-001-T06-REF03"

#: The registered revisions a native probe is drawn from (name -> file), besides T07's G8 corpus
#: and M02's C1 corpus, which are read through their test modules.
BENCHMARK_GLOBS: Final = (
    "benchmarks/s11/gp/*.json",
    "benchmarks/s11/thermal/*.json",
    "benchmarks/s11/flowsheets/*.json",
    "benchmarks/t08/ptc_r1/revision.json",
)

#: D-2: the admitted pairs no registered revision holds, constructed from a donor revision with a
#: stated feed and outlet pressures (feed: connection -> {T, P, n by component}; specs: id ->
#: value). Physically chosen states, not tuned: a failed solve is recorded as measured.
CONSTRUCTED: Final[Mapping[tuple[str, str], Mapping[str, Any]]] = {
    # Superheated steam, 1 bar -> 3 bar (T_sat(1 bar) = 372.76 K).
    ("thermal.compressor", "iapws95-v1"): {
        "donor": "file:benchmarks/s11/gp/GP-M1.json",
        "feed": {"S1": {"T": 400.0, "P": 100000.0, "n": {"H2O": 1.0}}},
        "specs": {"SPEC-M-P": 300000.0},
    },
    # Subcooled methanol-ethanol-water liquid at 300 K, 1 bar.
    ("syn001.stream_splitter", "wilson-ig-v2"): {
        "donor": "g8:SYN-001-T06-REF02",
        "feed": {"S1": {"T": 300.0, "P": 100000.0, "n": {"CH3OH": 0.3, "C2H5OH": 0.3, "H2O": 0.4}}},
        "specs": {},
    },
    # C1's routing splitter outside the coupled loop: SYN-001's splitter revision on the C1
    # vapour at the C1 heater's feed (M02's c1-heater.json).
    ("c1.stream_splitter", "pr-c1-v1"): {
        "donor": "g8:SYN-001-T06-REF02",
        "stands_in": "syn001.stream_splitter",
        "phases": {"S1": "vapor", "S2": "vapor", "S3": "vapor"},
        "feed": {
            "S1": {
                "T": 673.15,
                "P": 10000000.0,
                "n": {"H2": 0.6, "N2": 0.2, "NH3": 0.165, "Ar": 0.015, "CH4": 0.02},
            }
        },
        "specs": {},
    },
    # GP-M2 registers INITIALIZATION_FAILED (S11.A81: the expansion crosses the dew point); the
    # same turbine from 395 K (inside the records' 300-400 K, which the derivative witness probes
    # past at 400 K) to 1.25 bar keeps its isentropic state above the dew point.
    ("thermal.turbine", "wilson-ig-v2"): {
        "donor": "file:benchmarks/s11/gp/GP-M2.json",
        "feed": {"S1": {"T": 395.0, "P": 150000.0, "n": {"CH3OH": 0.4, "C2H5OH": 0.0, "H2O": 0.6}}},
        "specs": {"SPEC-M-P": 125000.0},
    },
    # R134a (T_sat(2 bar) = 263.07 K, T_sat(10 bar) = 312.5 K): the five thermal.* models and the
    # routing splitter no registered revision holds on CoolProp, each between a feed and sinks.
    ("thermal.flash", "coolprop-heos-v1"): {
        "donor": "file:benchmarks/s11/thermal/TH-V1.json",
        "feed": {"S1": {"T": 300.0, "P": 1000000.0, "n": {COOLPROP_FLUID: 1.0}}},
        "specs": {},
    },
    # TH-R1's loop on R134a: subcooled liquid at 5 bar (T_sat = 288.9 K), a smaller heater duty.
    ("thermal.mixer", "coolprop-heos-v1"): {
        "donor": "file:benchmarks/s11/thermal/TH-R1.json",
        "feed": {"S1": {"T": 280.0, "P": 500000.0, "n": {COOLPROP_FLUID: 1.0}}},
        "specs": {"SPEC-H-Q": 5000.0},
    },
    # TH-C1's Rankine cycle as an R134a ORC: liquid at 8 bar (T_sat = 304.5 K), pump to 30 bar
    # (below p_c = 40.6 bar), superheated to 440 K (the S07 range ends at 455 K) so the expansion
    # to 8 bar stays dry, so the turbine outlet is declared vapour (TH-C1's wet steam outlet is
    # vapor_liquid, which a single-phase isentropic state contradicts).
    **{
        (model_id, "coolprop-heos-v1"): {
            "donor": "file:benchmarks/s11/thermal/TH-C1.json",
            "phases": {"S4": "vapor"},
            "feed": {"S1": {"T": 300.0, "P": 800000.0, "n": {COOLPROP_FLUID: 1.0}}},
            "specs": {"SPEC-P-P": 3000000.0, "SPEC-B-T": 440.0, "SPEC-T-P": 800000.0},
        }
        for model_id in ("thermal.pump", "thermal.turbine")
    },
    ("syn001.stream_splitter", "coolprop-heos-v1"): {
        "donor": "g8:SYN-001-T06-REF02",
        "feed": {"S1": {"T": 250.0, "P": 500000.0, "n": {COOLPROP_FLUID: 1.0}}},
        "specs": {},
    },
}

#: What the register and the ADRs say about a pair the probe refuses, by the `_UNADMITTED` reason
#: its hint carries (None: R-288's plain rule). Register reading, not measurement.
REASON_REFERENCES: Final[Mapping[str | None, str]] = {
    None: "R-288 (a model binds on the bases MODEL_BASES lists; M02 design note §14.4 D3)",
    "gamma_phi": "R-288; L-GP-1 (S11 units design §4.5, §4.7: γ–φ faces for five units only)",
    "pure_fluid": "R-288; ADR 0051 (pure-fluid streams are declared-regime); S11 design §4.4",
    "c1_physics": "R-288; ADR 0050 D3 (the c1.* units carry pr-c1-v1's own physics)",
    "column_vapour": "R-631, R-760 (column allow-list); S02 §0 (pr-c1-v1 vapour-only)",
    "column_pure": "R-631; S11 design §4.7, §9 (a pure fluid has no stage composition)",
    "declared_regime": "R-288; ADR 0051; S11 units design §4.7",
    "lifted": "R-288; S11 units design §4.7 (lifted two-phase streams)",
    "no_volume": "R-819 (the pump stays refused on Wilson); L-GP-1",
    "no_entropy": "R-288; S11 units design §4.7 (thermal.* needs s)",
}

#: ADR 0056 row 9's question, per pair, from the register: was a refusal lifted by S10-C or S11
#: ("yes ..."), or kept by them ("no ...")? Pairs the register does not speak to are absent.
LIFTED: Final[Mapping[tuple[str, str], str]] = {
    ("syn001.column", "wilson-ig-v2"): (
        "yes: R-631 lifted for Wilson by S10-C (R-760, gamma-phi-ig-v1 allow-list) and S11 "
        "(design §4.7, §9 I1)"
    ),
    **{
        (model, "wilson-ig-v2"): "yes: S11 units design §4.5, §4.7 (track D, γ–φ faces)"
        for model in (
            "syn001.adiabatic_mixer",
            "syn001.ph_flash",
            "syn001.tp_flash",
            "syn001.tp_heater",
            "syn001.valve",
        )
    },
    ("thermal.compressor", "wilson-ig-v2"): "yes: S11 (R-819: refusing it rejected; L-GP-2)",
    ("thermal.turbine", "wilson-ig-v2"): "yes: S11 (R-819: refusing it rejected; L-GP-2)",
    ("syn001.liquid_pump", "wilson-ig-v2"): "no: R-819 keeps the pump refused on Wilson (X10)",
    ("thermal.pump", "wilson-ig-v2"): "no: R-819 keeps the pump refused on Wilson (X10)",
    ("syn001.column", "pr-c1-v1"): "no: R-760 leaves pr-c1-v1 under S11's cause (R-631)",
    ("syn001.column", "iapws95-v1"): "no: R-631 (no stage composition on a pure fluid)",
    ("syn001.column", "coolprop-heos-v1"): "no: R-631 (no stage composition on a pure fluid)",
}

Document = dict[str, Any]


# -- the axes -------------------------------------------------------------------------------------


def _binding() -> Any:
    from openflowsheet.application import revision_binding  # noqa: PLC0415

    return revision_binding


def models() -> list[str]:
    """Every model the revision path binds (`MODEL_BUILDERS`; `MODEL_BASES` has the same keys)."""
    binding = _binding()
    assert set(binding.MODEL_BASES) == set(binding.MODEL_BUILDERS)
    return sorted(binding.MODEL_BUILDERS)


def probe_bases() -> dict[str, Any]:
    """Provider id -> the basis that stands for it, in `SELECTABLE_BASES` order (CoolProp's by
    `COOLPROP_FLUID`)."""
    found: dict[str, Any] = {}
    for basis in _binding().SELECTABLE_BASES:
        if basis.provider_id == "coolprop-heos-v1" and basis.components != (COOLPROP_FLUID,):
            continue
        found.setdefault(basis.provider_id, basis)
    return found


def enumeration() -> dict[str, Any]:
    """The axes as the code holds them, with the scanned providers no `record_source` selects."""
    import pkgutil  # noqa: PLC0415

    import openflowsheet.thermo as thermo  # noqa: PLC0415
    from openflowsheet.models.revision_flowsheet import component_basis  # noqa: PLC0415

    binding = _binding()
    bases: dict[str, dict[str, Any]] = {}
    for basis in binding.SELECTABLE_BASES:
        entry = bases.setdefault(
            basis.provider_id,
            {"record_source": basis.record_source, "bases": 0, "components": []},
        )
        entry["bases"] += 1
        entry["components"].extend(c for c in basis.components if c not in entry["components"])
    for provider_id, entry in bases.items():
        if entry["bases"] > 1:
            entry["components"] = f"one per basis; probe fluid {COOLPROP_FLUID}"
        entry["probe_components"] = list(probe_bases()[provider_id].components)
    scanned: dict[str, dict[str, Any]] = {}
    for module in pkgutil.iter_modules(thermo.__path__):
        loaded = importlib.import_module(f"openflowsheet.thermo.{module.name}")
        provider_id = getattr(loaded, "PROVIDER_ID", None)
        if not isinstance(provider_id, str):
            continue
        row: dict[str, Any] = {"module": f"openflowsheet.thermo.{module.name}"}
        records = getattr(loaded, "RECORDS_PATH", None)
        if isinstance(records, str):
            # What a revision naming the provider's own records binds on (ADR 0034 D8).
            document = {"component_set": {"record_source": records}}
            row["records_path"] = records
            row["records_path_selects"] = component_basis(document).provider_id
        row["selectable"] = provider_id in bases
        scanned[provider_id] = row
    return {
        "provider_order": list(bases),
        "models": {
            model_id: {
                "family": model_id.split(".", 1)[0],
                "bases": sorted(binding.MODEL_BASES[model_id]),
            }
            for model_id in models()
        },
        "library_only_models": sorted(binding._LIBRARY_ONLY_HINTS),
        "bases": bases,
        "scanned_providers": scanned,
    }


# -- the registered revisions ---------------------------------------------------------------------


def corpus() -> dict[str, Callable[[], Document]]:
    """Name -> factory of a fresh copy of every registered revision a probe may use."""
    from m02_c1_corpus import C1_CORPUS  # noqa: PLC0415
    from t07_corpus import CORPUS  # noqa: PLC0415

    def _file(path: Path) -> Callable[[], Document]:
        return lambda: json.loads(path.read_text(encoding="utf-8"))

    found: dict[str, Callable[[], Document]] = {}
    found.update({f"g8:{name}": factory for name, factory in CORPUS.items()})
    found.update({f"m02:{name}": factory for name, factory in C1_CORPUS.items()})
    for pattern in BENCHMARK_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            found[f"file:{path.relative_to(ROOT).as_posix()}"] = _file(path)
    return found


def _provider_of(document: Mapping[str, Any]) -> str | None:
    from openflowsheet.models.revision_flowsheet import (  # noqa: PLC0415
        RevisionError,
        component_basis,
    )

    try:
        return component_basis(document).provider_id
    except RevisionError:
        return None


def index(documents: Mapping[str, Callable[[], Document]]) -> dict[str, Any]:
    """`(model, provider)` -> native revisions, and model -> every revision holding it; each list
    smallest first, by name on a tie."""
    native: dict[tuple[str, str], list[tuple[int, str]]] = {}
    holding: dict[str, list[tuple[int, str]]] = {}
    for name, factory in documents.items():
        document = factory()
        provider = _provider_of(document)
        size = len(document["instances"])
        for model_id in sorted({i["model"]["id"] for i in document["instances"]}):
            holding.setdefault(model_id, []).append((size, name))
            if provider is not None:
                native.setdefault((model_id, provider), []).append((size, name))
    return {
        "native": {key: [n for _, n in sorted(v)] for key, v in native.items()},
        "holding": {key: [n for _, n in sorted(v)] for key, v in holding.items()},
    }


# -- rebasing -------------------------------------------------------------------------------------


def _routing_swap(provider_id: str) -> dict[str, str]:
    """The routing models' namesakes on `provider_id`: C1's own on C1, SYN-001's elsewhere."""
    binding = _binding()
    pairs = [(s, c) for s, c in binding._NAMESAKES if s in binding.ROUTING_MODELS]
    if provider_id == "pr-c1-v1":
        return dict(pairs)
    return {c: s for s, c in pairs}


def rebase(
    document: Document,
    basis: Any,
    model_id: str,
    *,
    feed: Mapping[str, Mapping[str, Any]] | None = None,
    specs: Mapping[str, float] | None = None,
    stands_in: str | None = None,
    phases: Mapping[str, str] | None = None,
) -> Document:
    """`document` moved onto `basis`: its component set; each connection's component flows
    spread evenly over the basis' components (or `feed`'s, with its T and P); the routing models
    swapped for the basis' namesakes; the first instance of `model_id` (of `stands_in`, which it
    replaces, when given) moved to the front; the `phase_capability` of the connections `phases`
    names set to its value."""
    out = copy.deepcopy(document)
    for connection in out["connections"]:
        if phases and connection["id"] in phases:
            connection["phase_capability"] = phases[connection["id"]]
    components = list(basis.components)
    out["component_set"] = {"components": components, "record_source": basis.record_source}
    feed = feed or {}
    kept: list[Document] = []
    flows: dict[str, list[Document]] = {}
    for spec in out["specifications"]:
        target = spec["target"]
        if target.get("path") == "state.n" and target.get("component") is not None:
            flows.setdefault(target["object_id"], []).append(spec)
            continue
        override = feed.get(target.get("object_id"), {})
        if target.get("path") in ("state.T", "state.P") and target["path"][-1] in override:
            spec = {**spec, "value": float(override[target["path"][-1]])}
        if specs and spec["id"] in specs:
            spec = {**spec, "value": float(specs[spec["id"]])}
        kept.append(spec)
    for connection, rows in flows.items():
        total = sum(float(row["value"]) for row in rows)
        given = feed.get(connection, {}).get("n")
        for component in components:
            value = float(given[component]) if given else total / len(components)
            spec = copy.deepcopy(rows[0])
            spec["id"] = f"SPEC-{connection}-n-{component}"
            spec["target"]["component"] = component
            spec["value"] = value
            kept.append(spec)
    out["specifications"] = kept
    swap = _routing_swap(basis.provider_id)
    first = next(i for i in out["instances"] if i["model"]["id"] == (stands_in or model_id))
    first["model"]["id"] = model_id
    for instance in out["instances"]:
        if instance is not first and instance["model"]["id"] in swap:
            instance["model"]["id"] = swap[instance["model"]["id"]]
    out["instances"] = [first, *(i for i in out["instances"] if i is not first)]
    out["revision_id"] = f"X10-{model_id}-{basis.provider_id}"
    return out


# -- one probe ------------------------------------------------------------------------------------


def _unbound(unbound: Any) -> dict[str, Any]:
    return {
        "kind": unbound.kind,
        "code": unbound.detail,
        "hint": unbound.hint,
        "implicated": list(unbound.implicated),
    }


def _first_line(error: BaseException) -> str:
    text = str(error).strip().splitlines()
    return f"{type(error).__name__}: {text[0] if text else ''}"


def attempt(document: Document) -> dict[str, Any]:
    """Bind, route and (on `revision_eo`) solve one revision; every exception is recorded."""
    from m02_c1_corpus import surrogates  # noqa: PLC0415

    from openflowsheet.application.policies import (  # noqa: PLC0415
        DEFAULT_POLICY_ID,
        resolve_policy,
    )
    from openflowsheet.application.revision_binding import (  # noqa: PLC0415
        RevisionBinding,
        bind_revision_flowsheet,
    )
    from openflowsheet.application.revision_run import (  # noqa: PLC0415
        Route,
        select_route,
        solve_route,
    )
    from openflowsheet.verify.certificate import CheckPolicy  # noqa: PLC0415

    result: dict[str, Any] = {}
    try:
        bound = bind_revision_flowsheet(copy.deepcopy(document), surrogates=surrogates)
    except Exception as error:  # noqa: BLE001 — an untyped failure is a finding
        result["bind"] = {"error": _first_line(error)}
        return result
    result["bind"] = "bound" if isinstance(bound, RevisionBinding) else _unbound(bound)
    try:
        route = select_route(copy.deepcopy(document), surrogates=surrogates)
    except Exception as error:  # noqa: BLE001
        result["route"] = {"error": _first_line(error)}
        return result
    if not isinstance(route, Route):
        result["route"] = {"no_route": route.reason}
        return result
    result["route"] = {"solve_path": route.solve_path, "reason": route.reason}
    if route.solve_path != "revision_eo":
        # D-4: a coupled route needs the external unit's experiments; a legacy route is not the
        # revision path. Neither is solved here.
        return result
    policy = resolve_policy(DEFAULT_POLICY_ID, route.solve_path)
    assert policy is not None, route.solve_path
    try:
        run = solve_route(route, document, policy=policy, check_policy=CheckPolicy())
    except Exception as error:  # noqa: BLE001
        result["solve"] = {"error": _first_line(error)}
        return result
    solve: dict[str, Any] = {"outcome": run.outcome}
    if run.certificate is not None:
        solve["verification_status"] = run.certificate.verification_status
        solve["checks_not_passed"] = sorted(
            f"{check.id}:{check.result}"
            for check in run.certificate.checks
            if check.result != "pass"
        )
    if run.failure is not None:
        solve["failure"] = {
            "outcome": run.failure.outcome,
            "taxonomy": run.failure.taxonomy,
            "message": run.failure.observations.get("message"),
        }
    result["solve"] = solve
    return result


def classify(model_id: str, attempts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """The pair's class, from its last attempt (the first VERIFIED one, or the last tried)."""
    last = attempts[-1]
    bind = last["bind"]
    if isinstance(bind, Mapping) and "error" in bind:
        return {"class": "error", "detail": bind["error"]}
    if isinstance(bind, Mapping):
        code = bind["code"]
        if code.startswith("model_unsupported("):
            named = code[len("model_unsupported(") : -1]
            if named != model_id:
                return {"class": "unclassified", "detail": f"refusal names {named}"}
            return {"class": "refused_admission", "detail": code, "reason": _reason(bind)}
        if code.startswith(("basis_unavailable(", "basis_premises_unmet(")):
            return {"class": "refused_basis", "detail": code}
        return {"class": "refused_other", "detail": f"{bind['kind']}({code})"}
    route = last.get("route", {})
    if "error" in route:
        return {"class": "error", "detail": route["error"]}
    if "solve_path" in route and route["solve_path"] != "revision_eo":
        return {"class": "bound_not_solved", "detail": route["solve_path"]}
    solve = last.get("solve", {})
    if "error" in solve:
        return {"class": "error", "detail": solve["error"]}
    status = solve.get("verification_status")
    if status == "VERIFIED":
        return {"class": "solved_verified", "detail": solve["outcome"]}
    if status is not None:
        failed = ", ".join(c for c in solve["checks_not_passed"] if c.endswith(":fail"))
        detail = f"{solve['outcome']}/{status}" + (f" ({failed})" if failed else "")
        return {"class": "solved_not_verified", "detail": detail}
    return {"class": "solve_failed", "detail": solve.get("outcome")}


def _reason(bind: Mapping[str, Any]) -> str | None:
    """The `_UNADMITTED` key whose text the hint carries, or `None`."""
    hint = bind.get("hint") or ""
    for key, text in _binding()._UNADMITTED.items():
        if text.split("{", 1)[0] in hint:
            return str(key)
    return None


def _verified(outcome: Mapping[str, Any]) -> bool:
    return bool(outcome.get("solve", {}).get("verification_status") == "VERIFIED")


def probe(
    model_id: str, provider_id: str, documents: Mapping[str, Callable[[], Document]], found: Any
) -> dict[str, Any]:
    basis = probe_bases()[provider_id]
    attempts: list[dict[str, Any]] = []
    native = found["native"].get((model_id, provider_id), [])
    for name in native[:MAX_TRIES]:
        outcome = attempt(documents[name]())
        attempts.append({"revision": name, "probe": "native", **outcome})
        if _verified(outcome) or outcome["bind"] != "bound":
            break
    constructed = CONSTRUCTED.get((model_id, provider_id))
    if attempts and (_verified(attempts[-1]) or constructed is None):
        return {"attempts": attempts, **classify(model_id, attempts)}
    # D-2: no native revision, or none VERIFIED and a constructed one is registered.
    donor = constructed["donor"] if constructed else found["holding"][model_id][0]
    document = rebase(
        documents[donor](),
        basis,
        model_id,
        feed=constructed["feed"] if constructed else None,
        specs=constructed["specs"] if constructed else None,
        stands_in=constructed.get("stands_in") if constructed else None,
        phases=constructed.get("phases") if constructed else None,
    )
    outcome = attempt(document)
    kind = "constructed" if constructed else "rebased"
    attempts.append({"revision": donor, "probe": kind, **outcome})
    return {"attempts": attempts, **classify(model_id, attempts)}


# -- the inventory --------------------------------------------------------------------------------


def environment() -> str:
    return ENV_PRESENT if importlib.util.find_spec("CoolProp") is not None else ENV_ABSENT


def measure(selected: Sequence[str] | None = None) -> dict[str, Any]:
    """Every pair (or those of the models in `selected`) measured in this environment."""
    documents = corpus()
    found = index(documents)
    binding = _binding()
    env = environment()
    pairs: dict[str, Any] = {}
    for model_id in models():
        if selected and model_id not in selected:
            continue
        for provider_id in probe_bases():
            started = time.perf_counter()
            measured = probe(model_id, provider_id, documents, found)
            seconds = time.perf_counter() - started
            print(
                f"  {model_id} x {provider_id}: {measured['class']} ({seconds:.1f} s)",
                file=sys.stderr,
            )
            key = f"{model_id} x {provider_id}"
            pairs[key] = {
                "model": model_id,
                "provider": provider_id,
                "registry_admits": provider_id in binding.MODEL_BASES[model_id],
                "lifted_by_s10c_s11": LIFTED.get((model_id, provider_id)),
                "env": {env if provider_id == "coolprop-heos-v1" else ENV_ANY: measured},
            }
    return pairs


def _merge(recorded: Mapping[str, Any] | None, pairs: dict[str, Any]) -> dict[str, Any]:
    """`pairs` with the other environment's CoolProp measurements kept from `recorded`."""
    if recorded is None:
        return pairs
    for key, pair in pairs.items():
        old = recorded.get("pairs", {}).get(key)
        if old is None:
            continue
        for env, value in old["env"].items():
            pair["env"].setdefault(env, value)
    return pairs


def _summary(pairs: Mapping[str, Any]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for pair in pairs.values():
        for env, measured in pair["env"].items():
            bucket = counts.setdefault(env, {})
            bucket[measured["class"]] = bucket.get(measured["class"], 0) + 1
    return {env: dict(sorted(c.items())) for env, c in sorted(counts.items())}


def library_only() -> dict[str, dict[str, Any]]:
    """Each library-only model (`_LIBRARY_ONLY_HINTS`) bound on each probe basis: SYN-001's heater
    revision (G8 REF03) with the heater's instance naming the model instead."""
    documents = corpus()
    found: dict[str, dict[str, Any]] = {}
    for model_id in sorted(_binding()._LIBRARY_ONLY_HINTS):
        for provider_id, basis in probe_bases().items():
            document = rebase(
                documents[LIBRARY_ONLY_DONOR](), basis, model_id, stands_in="syn001.tp_heater"
            )
            bind = attempt(document)["bind"]
            found.setdefault(model_id, {})[provider_id] = bind
    return found


def document_of(pairs: dict[str, Any]) -> dict[str, Any]:
    body = {
        "library_only": library_only(),
        "schema": SCHEMA,
        "enumeration": enumeration(),
        "reason_references": {str(k): v for k, v in REASON_REFERENCES.items()},
        "probe": {"coolprop_fluid": COOLPROP_FLUID, "max_tries": MAX_TRIES},
        "pairs": dict(sorted(pairs.items())),
        "summary": _summary(pairs),
    }
    body["inventory_sha256"] = hashlib.sha256(_dumps(body).encode("utf-8")).hexdigest()
    return body


def _dumps(document: Mapping[str, Any]) -> str:
    return json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# -- the table ------------------------------------------------------------------------------------


def _cell(measured: Mapping[str, Any] | None) -> str:
    if measured is None:
        return "not measured"
    labels = {
        "solved_verified": "solved, VERIFIED",
        "solved_not_verified": "solved, not verified",
        "solve_failed": "admitted, solve failed",
        "bound_not_solved": "bound, not solved",
        "refused_admission": "refused (admission)",
        "refused_basis": "refused (basis)",
        "refused_other": "refused",
        "error": "ERROR",
        "unclassified": "UNCLASSIFIED",
    }
    return f"{labels[measured['class']]}: `{measured['detail']}`"


def render(document: Mapping[str, Any]) -> str:
    """`docs/X10-inventory.md`, generated from the inventory."""
    pairs = document["pairs"]
    providers = document["enumeration"]["provider_order"]
    lines = [
        "# X10 inventory: unit model × property basis, measured",
        "",
        "Generated by `scripts/x10_inventory.py` from `benchmarks/x10/inventory.json`;",
        "do not edit.",
        f"Inventory SHA-256 `{document['inventory_sha256']}`.",
        "",
        "ADR 0056 row 9 (R-925): which unit × basis pairs the revision path refuses today. Each",
        "pair is bound through `bind_revision_flowsheet` and `select_route`, and a bound",
        "`revision_eo` pair is solved once (default policy). How each probe revision is chosen,",
        "and what a class means: `docs/X10_DECISIONS.md`.",
        "",
        "## Counts",
        "",
        "| Environment | "
        + " | ".join(sorted({c for s in document["summary"].values() for c in s}))
        + " |",
    ]
    classes = sorted({c for s in document["summary"].values() for c in s})
    lines.append("| --- |" + " --- |" * len(classes))
    for env, counts in document["summary"].items():
        lines.append(f"| {env} | " + " | ".join(str(counts.get(c, 0)) for c in classes) + " |")
    lines += [
        "",
        "`any` is every pair off the CoolProp basis; the CoolProp column is measured with the",
        "optional `coolprop` extra absent and present.",
        "",
        "## Matrix",
        "",
        "| Model | " + " | ".join(providers) + " |",
        "| --- |" + " --- |" * len(providers),
    ]
    for model_id in document["enumeration"]["models"]:
        cells = []
        for provider_id in providers:
            pair = pairs.get(f"{model_id} x {provider_id}")
            if pair is None:
                cells.append("not measured")
                continue
            envs = pair["env"]
            if ENV_ANY in envs:
                cells.append(_short(envs[ENV_ANY]))
            else:
                absent, present = _short(envs.get(ENV_ABSENT)), _short(envs.get(ENV_PRESENT))
                cells.append(f"absent: {absent}; present: {present}")
        lines.append(f"| `{model_id}` | " + " | ".join(cells) + " |")
    lines += [
        "",
        "Cell key: **V** solved and VERIFIED; **U** solved, not verified; **F** admitted, solve",
        "failed; **B** bound on a route not solved here; **A** refused at admission",
        "(`model_unsupported`); **P** refused by the basis' provider preconditions; **R** another",
        "typed refusal; **E** error; **?** unclassified.",
        "",
        "## Every pair not solved and verified",
        "",
        "| Pair | Measured | Reason (register / ADR) | Lifted by S10-C/S11? |",
        "| --- | --- | --- | --- |",
    ]
    references = document["reason_references"]
    for key, pair in pairs.items():
        for env, measured in sorted(pair["env"].items()):
            if measured["class"] == "solved_verified":
                continue
            reason = ""
            if measured["class"] == "refused_admission":
                reason = references[str(measured.get("reason"))]
            elif measured["class"] == "refused_basis":
                reason = "S11 design §4.3 (provider preconditions)"
            elif measured["class"] == "bound_not_solved":
                reason = "not solved by the probe: the route needs the external unit's runs (D-4)"
            where = key if env == ENV_ANY else f"{key} ({env})"
            lifted = pair["lifted_by_s10c_s11"] or "not stated"
            lines.append(f"| `{where}` | {_cell(measured)} | {reason} | {lifted} |")
    lines += ["", "## Admitted pairs lifted by S10-C or S11", ""]
    for key, pair in pairs.items():
        if pair["registry_admits"] and pair["lifted_by_s10c_s11"]:
            lines.append(f"- `{key}`: {pair['lifted_by_s10c_s11']}")
    lines += ["", "## Providers and library-only models", ""]
    for provider_id, row in document["enumeration"]["scanned_providers"].items():
        selects = row.get("records_path_selects")
        note = "selectable" if row["selectable"] else "library-only"
        if selects is not None:
            note += f"; its records path `{row['records_path']}` selects `{selects}`"
        lines.append(f"- `{provider_id}` (`{row['module']}`): {note}")
    for model_id, refusals in document["library_only"].items():
        codes = sorted({row["code"] for row in refusals.values()})
        lines.append(
            f"- `{model_id}`: library-only model; on each of the {len(refusals)} providers "
            f"the binder returns {', '.join(f'`{c}`' for c in codes)}"
        )
    return "\n".join(lines) + "\n"


def _short(measured: Mapping[str, Any] | None) -> str:
    if measured is None:
        return "–"
    letter = {
        "solved_verified": "V",
        "solved_not_verified": "U",
        "solve_failed": "F",
        "bound_not_solved": "B",
        "refused_admission": "A",
        "refused_basis": "P",
        "refused_other": "R",
        "error": "E",
        "unclassified": "?",
    }[measured["class"]]
    return letter


# -- the command ----------------------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--record", action="store_true", help="measure and write both files")
    mode.add_argument("--check", action="store_true", help="measure and compare")
    parser.add_argument("--pairs", nargs="*", help="--check only: the models to re-measure")
    args = parser.parse_args(argv)
    recorded = json.loads(INVENTORY.read_text(encoding="utf-8")) if INVENTORY.exists() else None
    env = environment()
    if args.record:
        if args.pairs:
            parser.error("--record measures every pair")
        # Rendered from the written form, so the table reads the file's own key order.
        document = json.loads(_dumps(document_of(_merge(recorded, measure()))))
        INVENTORY.parent.mkdir(parents=True, exist_ok=True)
        INVENTORY.write_text(_dumps(document), encoding="utf-8")
        TABLE.write_text(render(document), encoding="utf-8")
        print(f"X10 inventory recorded ({env}): {json.dumps(document['summary'], sort_keys=True)}")
        return 0
    if recorded is None:
        print(f"X10 inventory: FAIL ({INVENTORY.relative_to(ROOT)} missing)")
        return 1
    failures: list[str] = []
    if document_of(copy.deepcopy(recorded["pairs"])) != recorded:
        failures.append("the recorded inventory is not its own regeneration")
    if render(recorded) != TABLE.read_text(encoding="utf-8"):
        failures.append(f"{TABLE.relative_to(ROOT)} is not the rendering of the inventory")
    axes = {f"{model_id} x {provider_id}" for model_id in models() for provider_id in probe_bases()}
    if axes != set(recorded["pairs"]):
        failures.append("the pair axes differ from the recorded ones")
    unknown = sorted(set(args.pairs or ()) - set(models()))
    if unknown:
        failures.append(f"--pairs names no model of MODEL_BUILDERS: {', '.join(unknown)}")
    fresh = measure(args.pairs)
    for key, pair in fresh.items():
        old = recorded["pairs"].get(key)
        if old is None:
            failures.append(f"{key}: not recorded")
            continue
        for field in ("registry_admits", "lifted_by_s10c_s11"):
            if pair[field] != old[field]:
                failures.append(f"{key}: {field} {old[field]!r} -> {pair[field]!r}")
        for env_key, measured in pair["env"].items():
            if old["env"].get(env_key) != measured:
                was = old["env"].get(env_key, {}).get("class")
                failures.append(f"{key} [{env_key}]: {was} -> {measured['class']}")
    if failures:
        print(f"X10 inventory: FAIL ({env}; {len(failures)} differences)")
        for line in failures:
            print(f"  {line}")
        return 1
    scope = f"{len(fresh)} pairs" + (" (subset)" if args.pairs else "")
    print(f"X10 inventory: PASS ({env}; {scope} re-measured equal)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
