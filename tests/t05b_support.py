"""Shared support for T05b's tests: the registered reference, and the case revisions of §12.

Not collected as tests. Every expected number comes from `benchmarks/t05b/reference_values.yaml`
(the design lane's 40-digit twin, T05b spec header), read here once; no test copies a registered
value into its source. The revisions are built from T05's instances (`SYN-001-UL-C1.yaml` and its
siblings) with the pinned values and configuration the spec states (§12.3–§12.5), by the same
templates T05 W12's `mini_revision` uses, generalized to a chain of units.
"""

from __future__ import annotations

import copy
import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from conftest import load_yaml
from t05_w12_support import connection_pin, duty_pin, planned_step, unit_instance
from test_t05_w11_cases import case_document

from openflowsheet.application.policies import T05B_V2
from openflowsheet.application.revision_binding import RevisionBinding
from openflowsheet.compile.casadi_backend import compile_problem
from openflowsheet.compiled import EvaluationContext
from openflowsheet.orchestrator import revision as revision_module
from openflowsheet.orchestrator.mass import residence_time
from openflowsheet.orchestrator.region import RegionResult, solve_region
from openflowsheet.orchestrator.splits import (
    closure_types,
    dormancy_forms,
    lifted_splits,
    split_temperatures,
    zero_flow_forms,
)
from openflowsheet.orchestrator.trace import SolvePolicy, Trace
from openflowsheet.thermo import (
    FlashRequest,
    FlashResult,
    PropertyCapabilities,
    PropertyProvider,
    PropertyRequest,
    PropertyResult,
    StreamState,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REF: dict[str, Any] = load_yaml(REPO_ROOT / "benchmarks" / "t05b" / "reference_values.yaml")

#: Spec §6.6: the policy every T05b case runs, `T05-W13` with the second phase-contract literal.
#: The one construction of v2 outside `test_t05b_literal.py` (B06 checks both) is
#: `openflowsheet.application.policies.T05B_V2`, where T07 W3a moved it (W0 flag E6).
POLICY_V2: SolvePolicy = T05B_V2

Document = dict[str, Any]

#: The reference pressure every T05b case is registered at, Pa.
P_R = 1.0e5


def number(value: str) -> float:
    """A registered 20-digit string as the double it rounds to."""
    return float(Decimal(value))


def error(got: float, expected: str) -> float:
    """`|got - expected|` with the registered string taken at its full precision."""
    return float(abs(Decimal(got) - Decimal(expected)))


# -- revisions: sources -> a chain of units -> sinks ----------------------------------------


@dataclass(frozen=True)
class Source:
    """A fresh feed `stream` into `unit.port`, fully specified."""

    stream: str
    unit: str
    port: str
    capability: str
    flows: tuple[float, float, float]
    temperature: float
    pressure: float


@dataclass(frozen=True)
class Link:
    """A connection between two units of the chain."""

    stream: str
    source: tuple[str, str]
    target: tuple[str, str]
    capability: str


@dataclass(frozen=True)
class Product:
    """A unit's outlet `stream` into its own product sink."""

    stream: str
    source: tuple[str, str]
    capability: str


_C1 = case_document("SYN-001-UL-C1")


def _find(items: Sequence[Document], identifier: str) -> Document:
    (found,) = (item for item in items if item["id"] == identifier)
    return found


def instance(case: str, unit: str, identifier: str | None = None) -> Document:
    """A registered case's instance, copied, optionally under a new id."""
    document = unit_instance(case, unit)
    if identifier is not None:
        document["id"] = identifier
    return document


def revision(
    name: str,
    units: Sequence[Document],
    sources: Sequence[Source],
    links: Sequence[Link],
    products: Sequence[Product],
    pins: Sequence[Document],
) -> Document:
    """C1's document with the given units, feeds, internal connections, sinks and pins.

    Feed `k` is `U-FEED-<k>` with C1's feed specifications retargeted and revalued; the sink of
    product `k` is `U-SINK-<k>`. Connections are declared feeds first, then links, then products.
    Everything else (schema version, components, provenance) is C1's."""
    document = copy.deepcopy(_C1)
    document["revision_id"] = f"T05b-{name}"
    document["title"] = f"T05b test fixture: {name}"
    feed, sink = _find(_C1["instances"], "U-FEED"), _find(_C1["instances"], "U-SINK-V")
    template = _find(_C1["connections"], "S1")
    feed_specifications = {
        path: _find(_C1["specifications"], f"SPEC-feed-{path}")
        for path in ("n-A", "n-B", "n-C", "T", "P")
    }

    def connection(stream: str, capability: str, source: Document, target: Document) -> Document:
        return dict(
            copy.deepcopy(template),
            id=stream,
            phase_capability=capability,
            **{"from": source},
            to=target,
        )

    instances: list[Document] = [*units]
    connections: list[Document] = []
    specifications: list[Document] = []
    for k, entry in enumerate(sources):
        feed_id = f"U-FEED-{k}"
        instances.append(dict(copy.deepcopy(feed), id=feed_id))
        connections.append(
            connection(
                entry.stream,
                entry.capability,
                {"instance": feed_id, "port": "outlet"},
                {"instance": entry.unit, "port": entry.port},
            )
        )
        values = {
            "n-A": entry.flows[0],
            "n-B": entry.flows[1],
            "n-C": entry.flows[2],
            "T": entry.temperature,
            "P": entry.pressure,
        }
        for path, specification in feed_specifications.items():
            spec = copy.deepcopy(specification)
            spec["id"] = f"SPEC-{entry.stream}-{path}"
            spec["target"]["object_id"] = entry.stream
            spec["value"] = values[path]
            specifications.append(spec)
    for link in links:
        connections.append(
            connection(
                link.stream,
                link.capability,
                {"instance": link.source[0], "port": link.source[1]},
                {"instance": link.target[0], "port": link.target[1]},
            )
        )
    for k, product in enumerate(products):
        sink_id = f"U-SINK-{k}"
        instances.append(dict(copy.deepcopy(sink), id=sink_id))
        connections.append(
            connection(
                product.stream,
                product.capability,
                {"instance": product.source[0], "port": product.source[1]},
                {"instance": sink_id, "port": "inlet"},
            )
        )
    document.update(
        instances=instances, connections=connections, specifications=[*specifications, *pins]
    )
    return document


# -- §12.3: one flowing component on the EO path --------------------------------------------

PURE_B = (0.0, 2.0, 0.0)


def sc1() -> Document:
    """Feed `(0,2,0)` 370 K 1.8e5 Pa liquid → `U-VLV` (`P_spec = P_r`) → `S2` lifted → sink."""
    return revision(
        "SC-1",
        [instance("SYN-001-UL-C1", "U-VLV")],
        [Source("S1", "U-VLV", "inlet", "liquid", PURE_B, 370.0, 1.8e5)],
        [],
        [Product("S2", ("U-VLV", "outlet"), "vapor_liquid")],
        [connection_pin("SPEC-valve-P", "S2", "state.P", P_R)],
    )


def sc2() -> Document:
    """Feed `(0,2,0)` 300 K `P_r` liquid → `U-PHF` (`Q = 42 000 W`, `ΔP = 0`) → `S2`, `S3`."""
    return revision(
        "SC-2",
        [instance("SYN-001-UL-C1", "U-PHF")],
        [Source("S1", "U-PHF", "inlet", "liquid", PURE_B, 300.0, P_R)],
        [],
        [Product("S2", ("U-PHF", "vapor"), "vapor"), Product("S3", ("U-PHF", "liquid"), "liquid")],
        [duty_pin("SPEC-phf-Q", "U-PHF", 42_000.0)],
    )


def sc3() -> Document:
    """SC-1's feed and valve; `S2` (lifted) → `U-PHF` (`Q = −1 000 W`) → `S3` vap, `S4` liq."""
    return revision(
        "SC-3",
        [instance("SYN-001-UL-C1", "U-VLV"), instance("SYN-001-UL-C1", "U-PHF")],
        [Source("S1", "U-VLV", "inlet", "liquid", PURE_B, 370.0, 1.8e5)],
        [Link("S2", ("U-VLV", "outlet"), ("U-PHF", "inlet"), "vapor_liquid")],
        [Product("S3", ("U-PHF", "vapor"), "vapor"), Product("S4", ("U-PHF", "liquid"), "liquid")],
        [
            connection_pin("SPEC-valve-P", "S2", "state.P", P_R),
            duty_pin("SPEC-phf-Q", "U-PHF", -1_000.0),
        ],
    )


def sc4() -> Document:
    """Feed `(0,2,0)` 300 K liquid → `U-PHF1` (`Q = 42 000 W`) → `S2` vap → `U-PHF2` (declared
    `VAPOR` inlet, `Q = −15 000 W`) → `S4` vap, `S5` liq; `U-PHF1`'s `S3` liq → `U-PUMP`
    (`P_out = 1.5e5 Pa`, η = 0.75) → `S6` → sink."""
    return revision(
        "SC-4",
        [
            instance("SYN-001-UL-C1", "U-PHF", "U-PHF1"),
            instance("SYN-001-UL-C1", "U-PHF", "U-PHF2"),
            instance("SYN-001-UL-C1", "U-PUMP"),
        ],
        [Source("S1", "U-PHF1", "inlet", "liquid", PURE_B, 300.0, P_R)],
        [
            Link("S2", ("U-PHF1", "vapor"), ("U-PHF2", "inlet"), "vapor"),
            Link("S3", ("U-PHF1", "liquid"), ("U-PUMP", "inlet"), "liquid"),
        ],
        [
            Product("S4", ("U-PHF2", "vapor"), "vapor"),
            Product("S5", ("U-PHF2", "liquid"), "liquid"),
            Product("S6", ("U-PUMP", "outlet"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf1-Q", "U-PHF1", 42_000.0),
            duty_pin("SPEC-phf2-Q", "U-PHF2", -15_000.0),
            connection_pin("SPEC-pump-P", "S6", "state.P", 1.5e5),
        ],
    )


SINGLE_COMPONENT_CASES = {"SC-1": sc1, "SC-2": sc2, "SC-3": sc3, "SC-4": sc4}


def sc1_root() -> dict[str, float]:
    """SC-1's registered root over its declaration's columns: the feed as §12.3 pins it, `S2` as
    `ref.single_component_cases.SC-1.root`."""
    root = REF["single_component_cases"]["SC-1"]["root"]["S2"]
    state: dict[str, float] = {"S1.T": 370.0, "S1.P": 1.8e5}
    for index, c in enumerate("ABC"):
        state[f"S1.n.{c}"] = PURE_B[index]
        state[f"S2.n.{c}"] = number(root["n_mol_per_s"][index])
        state[f"S2.vap.{c}"] = number(root["vapor_mol_per_s"][index])
        state[f"S2.liq.{c}"] = number(root["liquid_mol_per_s"][index])
    state["S2.T"] = number(root["T_K"])
    state["S2.P"] = number(root["P_Pa"])
    state["S2.V"] = sum(state[f"S2.vap.{c}"] for c in "ABC")
    state["S2.L"] = sum(state[f"S2.liq.{c}"] for c in "ABC")
    return state


def prj_b2() -> dict[str, float]:
    """K04-F9 PRJ-B2 (the former INJ-B2; `ref.closed_form.cases.PRJ-B2`): SC-1's root with
    `S2.T = 360.000002 K`, the lever-rule split kept — every compiled row inside its tolerance,
    2 `τ_T` from the root (K04-F9 finding F1)."""
    state = sc1_root()
    state["S2.T"] = 360.000002
    return state


def inj_b2_prime() -> dict[str, float]:
    """K04-F9 INJ-B2′ (`ref.closed_form.injections.INJ-B2-prime`): SC-1's root with
    `S2.T = 360.00002 K`, the lever-rule split kept — the degeneracy window's outer side."""
    state = sc1_root()
    state["S2.T"] = 360.00002
    return state


# -- §12.4: near-pure feeds on the EO path ---------------------------------------------------


def near_pure_inputs(case: str) -> tuple[tuple[float, float, float], float]:
    """`(n, Q_spec)` of `ref.near_pure_cases.<case>`, read from its registered flowsheet line."""
    import re

    text = REF["near_pure_cases"][case]["flowsheet"]
    flows = re.search(r"U-FEED \[([^\]]*)\]", text)
    duty = re.search(r"Q_spec = (\S+) W", text)
    assert flows is not None and duty is not None, text
    n = tuple(number(value.strip(" '")) for value in flows.group(1).split(","))
    assert len(n) == 3, text
    return (n[0], n[1], n[2]), number(duty.group(1))


def near_pure(case: str) -> Document:
    """Feed `n` 300 K `P_r` liquid → `U-PHF` (`Q_spec`, `ΔP = 0`, inlet LIQUID) → `S2`, `S3`."""
    flows, duty = near_pure_inputs(case)
    return revision(
        case,
        [instance("SYN-001-UL-C1", "U-PHF")],
        [Source("S1", "U-PHF", "inlet", "liquid", flows, 300.0, P_R)],
        [],
        [Product("S2", ("U-PHF", "vapor"), "vapor"), Product("S3", ("U-PHF", "liquid"), "liquid")],
        [duty_pin("SPEC-phf-Q", "U-PHF", duty)],
    )


NEAR_PURE_CASES = ("NP-1", "NP-2", "NP-3", "NP-G")


def np_gc() -> Document:
    """K04-F9 NP-GC (`ref.closed_form.cases.NP-GC`): NP-G's flowsheet with its liquid product
    `S3` split in two by `U-SPLIT` (`split_fraction 0.5`) → `S4` (recycle port), `S5` (purge),
    each to its own sink — D2's load-bearing case, two copies of a saturated product."""
    flows, duty = near_pure_inputs("NP-G")
    splitter = instance("SYN-001-UL-C3", "U-SPLIT")
    splitter["parameters"]["split_fraction"]["value"] = 0.5
    return revision(
        "NP-GC",
        [instance("SYN-001-UL-C1", "U-PHF"), splitter],
        [Source("S1", "U-PHF", "inlet", "liquid", flows, 300.0, P_R)],
        [Link("S3", ("U-PHF", "liquid"), ("U-SPLIT", "inlet"), "liquid")],
        [
            Product("S2", ("U-PHF", "vapor"), "vapor"),
            Product("S4", ("U-SPLIT", "recycle"), "liquid"),
            Product("S5", ("U-SPLIT", "purge"), "liquid"),
        ],
        [duty_pin("SPEC-phf-Q", "U-PHF", duty)],
    )


# -- §12.5, §12.9: dormant PH-type outlets and the lifted zero-flow conflict ------------------

#: The dormant feed of DZ-1, DZ-2, DZ-4, DZ-5 and DZ-2C: `(0, 0, 0)` at 330 K and `P_r`.
DORMANT_FEED = (0.0, 0.0, 0.0)


def dz1() -> Document:
    """Feed `(0,0,0)` 330 K `P_r` liquid → `U-VLV` (`P_spec = 9e4 Pa`) → `S2` → sink."""
    return revision(
        "DZ-1",
        [instance("SYN-001-UL-C1", "U-VLV")],
        [Source("S1", "U-VLV", "inlet", "liquid", DORMANT_FEED, 330.0, P_R)],
        [],
        [Product("S2", ("U-VLV", "outlet"), "vapor_liquid")],
        [connection_pin("SPEC-valve-P", "S2", "state.P", 9.0e4)],
    )


def dz2(duty: float = 0.0, name: str = "DZ-2") -> Document:
    """Feed as DZ-1 → `U-PHF` (`Q = duty`, `ΔP = 0`) → `S2` vap, `S3` liq; DZ-2C at 1 000 W."""
    return revision(
        name,
        [instance("SYN-001-UL-C1", "U-PHF")],
        [Source("S1", "U-PHF", "inlet", "liquid", DORMANT_FEED, 330.0, P_R)],
        [],
        [Product("S2", ("U-PHF", "vapor"), "vapor"), Product("S3", ("U-PHF", "liquid"), "liquid")],
        [duty_pin("SPEC-phf-Q", "U-PHF", duty)],
    )


def dz2c() -> Document:
    """DZ-2 with `Q_spec = 1 000 W` (spec §12.9), read from `ref.zero_flow_conflicts.DZ-2C`."""
    return dz2(number(REF["zero_flow_conflicts"]["DZ-2C"]["Q_spec_W"]), "DZ-2C")


def dz3() -> Document:
    """Feed `(1,1,1)` 300 K → `U-PHF` (`Q = 50 000 W`, PHF-1) → `S2` vap → sink; `S3` liq →
    `U-SPLIT` (`r = 0`) → `S4` (recycle, dormant) → `U-VLV` (`P_spec = 9e4`, inlet LIQUID) →
    `S5` → sink; `S6` (purge) → sink."""
    splitter = instance("SYN-001-UL-C3", "U-SPLIT")
    splitter["parameters"]["split_fraction"]["value"] = 0.0
    return revision(
        "DZ-3",
        [instance("SYN-001-UL-C1", "U-PHF"), splitter, instance("SYN-001-UL-C1", "U-VLV")],
        [Source("S1", "U-PHF", "inlet", "liquid", (1.0, 1.0, 1.0), 300.0, P_R)],
        [
            Link("S3", ("U-PHF", "liquid"), ("U-SPLIT", "inlet"), "liquid"),
            Link("S4", ("U-SPLIT", "recycle"), ("U-VLV", "inlet"), "liquid"),
        ],
        [
            Product("S2", ("U-PHF", "vapor"), "vapor"),
            Product("S5", ("U-VLV", "outlet"), "vapor_liquid"),
            Product("S6", ("U-SPLIT", "purge"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", 50_000.0),
            connection_pin("SPEC-valve-P", "S5", "state.P", 9.0e4),
        ],
    )


def dz4() -> Document:
    """Feed as DZ-1 → `U-RX` (C2's: `ν = (−2,−1,3)`, key A, `X = 0.5`, `ΔP = 0`; configuration
    `energy_specification = duty` by its duty pin, `Q_spec = 0`) → `S2` → sink."""
    return revision(
        "DZ-4",
        [instance("SYN-001-UL-C2", "U-RX")],
        [Source("S1", "U-RX", "inlet", "liquid", DORMANT_FEED, 330.0, P_R)],
        [],
        [Product("S2", ("U-RX", "outlet"), "vapor_liquid")],
        [duty_pin("SPEC-rx-Q", "U-RX", 0.0)],
    )


def dz5() -> Document:
    """Feed as DZ-1 → `U-HEAT` (`T_spec = 350 K`) → `S2` → sink: a TP-type split."""
    return revision(
        "DZ-5",
        [instance("SYN-001-UL-C1", "U-HEAT")],
        [Source("S1", "U-HEAT", "inlet", "liquid", DORMANT_FEED, 330.0, P_R)],
        [],
        [Product("S2", ("U-HEAT", "outlet"), "vapor_liquid")],
        [connection_pin("SPEC-heater-T", "S2", "state.T", 350.0)],
    )


DORMANT_CASES = {"DZ-1": dz1, "DZ-2": dz2, "DZ-3": dz3, "DZ-4": dz4, "DZ-5": dz5, "DZ-2C": dz2c}


# -- §12.8, §12.9: dormant non-lifted outlets and the non-lifted zero-flow conflict -----------

#: K05's twin names its second feed `U-FEED2`; `revision` names feed `k` `U-FEED-<k>`.
_REGISTERED_FEEDS = {"U-FEED-0:": "U-FEED:", "U-FEED-1:": "U-FEED2:"}


def registered_name(name: str) -> str:
    """A case revision's row id as `ref` names it (`U-FEED-0` → `U-FEED`, `U-FEED-1` →
    `U-FEED2`); every other id is the same in both."""
    for ours, theirs in _REGISTERED_FEEDS.items():
        if name.startswith(ours):
            return theirs + name[len(ours) :]
    return name


def dz6() -> Document:
    """Feed `(0,0,0)` 330 K `P_r` liquid → `U-PUMP` (C1's: η = 0.75; `P_out = 1.5e5 Pa`) → `S2`
    → sink."""
    return revision(
        "DZ-6",
        [instance("SYN-001-UL-C1", "U-PUMP")],
        [Source("S1", "U-PUMP", "inlet", "liquid", DORMANT_FEED, 330.0, P_R)],
        [],
        [Product("S2", ("U-PUMP", "outlet"), "liquid")],
        [connection_pin("SPEC-pump-P", "S2", "state.P", 1.5e5)],
    )


def _exchanger(
    name: str,
    hot: tuple[tuple[float, float, float], float],
    cold: tuple[tuple[float, float, float], float],
    specification: Document,
) -> Document:
    """Feed `hot` → `S1` → `U-HX` hot side → `S2` → sink; feed `cold` → `S3` → cold side → `S4`
    → sink; both sides declared `LIQUID`; C3's exchanger under the given specification pin."""
    return revision(
        name,
        [instance("SYN-001-UL-C3", "U-HX")],
        [
            Source("S1", "U-HX", "hot_inlet", "liquid", hot[0], hot[1], P_R),
            Source("S3", "U-HX", "cold_inlet", "liquid", cold[0], cold[1], P_R),
        ],
        [],
        [
            Product("S2", ("U-HX", "hot_outlet"), "liquid"),
            Product("S4", ("U-HX", "cold_outlet"), "liquid"),
        ],
        [specification],
    )


def dz7(duty: float = 0.0, name: str = "DZ-7") -> Document:
    """A dormant hot side at 290 K beside a flowing cold side `(1,1,1)` at 300 K, duty `Q_spec`
    (0 W; DZ-11: 1 000 W)."""
    return _exchanger(
        name,
        (DORMANT_FEED, 290.0),
        ((1.0, 1.0, 1.0), 300.0),
        duty_pin("SPEC-hx-Q", "U-HX", duty),
    )


def dz8() -> Document:
    """Both sides dormant (hot 350 K, cold 300 K); `hot_outlet_temperature = 345 K`."""
    return _exchanger(
        "DZ-8",
        (DORMANT_FEED, 350.0),
        (DORMANT_FEED, 300.0),
        connection_pin("SPEC-hx-hot-T", "S2", "state.T", 345.0),
    )


def dz9(*, mixer_first: bool = False) -> Document:
    """Feeds `(0,0,0)` 330 K → `S1` and `(0,0,0)` 310 K → `S2` into C2's `U-MIX`, wired in that
    order → `S3` → sink.

    The feeds are declared before the mixer, as the twin declares them: which of the two
    redundant pressure rows T01's certificate and K03's alias elimination remove follows
    declaration order (W0.11 (b), measured: `U-MIX:MIX-pressure:1` feeds first, the second feed's
    `FEED-P` mixer first), and `ref…DZ-9` registers the former. `mixer_first` declares the mixer
    before the feeds (spec B24's order variant, ruled 2026-09-25, Q-S4 (1))."""
    document = revision(
        "DZ-9",
        [instance("SYN-001-UL-C2", "U-MIX")],
        [
            Source("S1", "U-MIX", "inlet", "liquid", DORMANT_FEED, 330.0, P_R),
            Source("S2", "U-MIX", "inlet", "liquid", DORMANT_FEED, 310.0, P_R),
        ],
        [],
        [Product("S3", ("U-MIX", "outlet"), "liquid")],
        [],
    )
    if mixer_first:
        return document
    instances = document["instances"]
    feeds = [entry for entry in instances if entry["id"].startswith("U-FEED-")]
    document["instances"] = [*feeds, *(entry for entry in instances if entry not in feeds)]
    return document


def dz10() -> Document:
    """DZ-3 with `U-VLV` replaced by C1's `U-PUMP`: the splitter's dormant recycle `S4` → pump
    (`P_out = 1.5e5 Pa`) → `S5` → sink."""
    splitter = instance("SYN-001-UL-C3", "U-SPLIT")
    splitter["parameters"]["split_fraction"]["value"] = 0.0
    return revision(
        "DZ-10",
        [instance("SYN-001-UL-C1", "U-PHF"), splitter, instance("SYN-001-UL-C1", "U-PUMP")],
        [Source("S1", "U-PHF", "inlet", "liquid", (1.0, 1.0, 1.0), 300.0, P_R)],
        [
            Link("S3", ("U-PHF", "liquid"), ("U-SPLIT", "inlet"), "liquid"),
            Link("S4", ("U-SPLIT", "recycle"), ("U-PUMP", "inlet"), "liquid"),
        ],
        [
            Product("S2", ("U-PHF", "vapor"), "vapor"),
            Product("S5", ("U-PUMP", "outlet"), "liquid"),
            Product("S6", ("U-SPLIT", "purge"), "liquid"),
        ],
        [
            duty_pin("SPEC-phf-Q", "U-PHF", 50_000.0),
            connection_pin("SPEC-pump-P", "S5", "state.P", 1.5e5),
        ],
    )


def dz11() -> Document:
    """DZ-7 with `Q_spec = 1 000 W` (spec §12.9), read from `ref.zero_flow_conflicts.DZ-11`."""
    return dz7(number(REF["zero_flow_conflicts"]["DZ-11"]["Q_spec_W"]), "DZ-11")


def dz12() -> Document:
    """Feed `(1,1,1)` 300 K → `U-PHF` (`Q = 30 000 W`) → `S2` vap → `U-HX` hot side (`VAPOR`) →
    `S4` → sink, `S3` liq → sink; feed `(1,1,1)` 300 K → `S5` → cold side → `S6` → sink; duty 0."""
    return revision(
        "DZ-12",
        [instance("SYN-001-UL-C1", "U-PHF"), instance("SYN-001-UL-C3", "U-HX")],
        [
            Source("S1", "U-PHF", "inlet", "liquid", (1.0, 1.0, 1.0), 300.0, P_R),
            Source("S5", "U-HX", "cold_inlet", "liquid", (1.0, 1.0, 1.0), 300.0, P_R),
        ],
        [Link("S2", ("U-PHF", "vapor"), ("U-HX", "hot_inlet"), "vapor")],
        [
            Product("S3", ("U-PHF", "liquid"), "liquid"),
            Product("S4", ("U-HX", "hot_outlet"), "vapor"),
            Product("S6", ("U-HX", "cold_outlet"), "liquid"),
        ],
        [duty_pin("SPEC-phf-Q", "U-PHF", 30_000.0), duty_pin("SPEC-hx-Q", "U-HX", 0.0)],
    )


DORMANT_NON_LIFTED_CASES = {
    "DZ-6": dz6,
    "DZ-7": dz7,
    "DZ-8": dz8,
    "DZ-9": dz9,
    "DZ-10": dz10,
    "DZ-12": dz12,
    "DZ-11": dz11,
}


def registered_state(entry: Mapping[str, Any]) -> dict[str, float]:
    """A registered `{column: 20-digit string}` state as doubles, over the case revision's
    columns (`revision` names its feed `U-FEED-0`; the registry names it `U-FEED`)."""
    return {
        column.replace("U-FEED:", "U-FEED-0:", 1): number(value) for column, value in entry.items()
    }


def solve_from_v2(
    binding: RevisionBinding,
    state: Mapping[str, float],
    policy: SolvePolicy = POLICY_V2,
    trace: Trace | None = None,
) -> RegionResult:
    """`t05_w12_support.solve_from` with the region's T05b inputs — the closure types, the
    `ZERO_FLOW` forms, the dormancy forms and the split temperatures `executor._region` passes
    (spec §6.1, §6.2, §7.6) — for a
    start the traversal cannot give (DZ-3's and DZ-10's perturbed starts; DZ-12's liquid-form root;
    DZ-2C and DZ-11, whose traversals refuse)."""
    step = planned_step(binding, policy)
    flowsheet, spec = binding.flowsheet, binding.spec
    missing = [column for column in spec.variable_ids if column not in state]
    assert not missing, f"the start has no value for {missing}"
    assert step.region is not None
    instances = revision_module.instances_of(flowsheet)
    splits = lifted_splits(instances, flowsheet.components)
    types = closure_types(flowsheet.units())
    return solve_region(
        compiled=compile_problem(spec),
        spec=spec,
        region=step.region,
        state={column: state[column] for column in spec.variable_ids},
        splits=splits,
        provider=flowsheet.provider,
        policy=policy,
        initializer_source="user_guess",
        mass_mapping=residence_time(flowsheet.wiring, flowsheet.components),
        closure_types=types,
        zero_flow_forms=zero_flow_forms(instances, splits, types, flowsheet.components),
        dormancy_forms=dormancy_forms(instances, flowsheet.units(), flowsheet.components),
        split_temperatures=split_temperatures(instances, splits),
        trace=trace,
    )


# -- §12.2: the provider test doubles -------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Jump:
    """JUMP (spec §12.2): every vapour enthalpy raised by 1 000 J/mol above 360 K.

    `evaluate_phase` only; the flash, `lnK` and the liquid enthalpies are SYN-001's. It violates
    the provider class's continuity, so no route can meet a target inside the jump."""

    inner: PropertyProvider
    above: float = 360.0
    step: float = 1_000.0

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        result = self.inner.evaluate_phase(request, context)
        if request.phase != "VAPOR" or not request.state.temperature > self.above:
            return result
        values = {
            name: value + self.step if name.startswith("h_") else value
            for name, value in result.values.items()
        }
        return dataclasses.replace(result, values=values)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        return self.inner.flash(request, context)


@dataclasses.dataclass(frozen=True)
class Biased:
    """BIASED (spec §12.2): SYN-001 whose TP flash returns `β + 1e-5` when it is two-phase.

    The split is recomputed from the biased `β` as the twin's `biased_split` does:
    `x_i = z_i/(1 + β(K_i − 1))`, `v_i = β N K_i x_i`, `l_i = n_i − v_i`."""

    inner: PropertyProvider
    bias: float = 1e-5

    def describe(self) -> PropertyCapabilities:
        return self.inner.describe()

    def evaluate_phase(
        self, request: PropertyRequest, context: EvaluationContext
    ) -> PropertyResult:
        return self.inner.evaluate_phase(request, context)

    def flash(self, request: FlashRequest, context: EvaluationContext) -> FlashResult:
        result = self.inner.flash(request, context)
        if result.phase_signature != "TWO_PHASE" or result.vapor is None:
            return result
        n = request.state.n
        total = sum(n)
        beta = sum(result.vapor.n) / total + self.bias
        k = [result.k_values[name] for name in self.inner.describe().components]
        x = [(flow / total) / (1.0 + beta * (k[i] - 1.0)) for i, flow in enumerate(n)]
        vapor = tuple(beta * total * k[i] * x[i] for i in range(len(n)))
        liquid = tuple(flow - v for flow, v in zip(n, vapor, strict=True))
        temperature, pressure = request.state.temperature, request.state.pressure
        return dataclasses.replace(
            result,
            vapor_fraction=beta,
            vapor=StreamState(n=vapor, temperature=temperature, pressure=pressure),
            liquid=StreamState(n=liquid, temperature=temperature, pressure=pressure),
        )


# -- K04-F9 (ADR 0013 D1): where the verifier judged, read back by the tests ----------------------

#: K04-F9 spec §5.5's fixed list.
PROJECTED = ["energy_balance", "phase_admissibility", "independent_split"]


def judged_where(certificate: Any, judged_at: str, reason: str = "") -> None:
    """X01: `transformations.projection` in spec §5.5's grammar, with the given point."""
    assert certificate.transformations["projection"] == {
        "judged_at": judged_at,
        "reason": reason,
        "categories": PROJECTED,
    }


def fresh_flash_ratios(checks: Sequence[Any]) -> dict[str, float]:
    """`|value| / tolerance` of every evaluated fresh-flash check (spec §5.1's projected
    categories). A one-sided bubble or dew check on the admissible side records its margin, not a
    deviation, and is left out (`value ≤ 0` there)."""
    ratios: dict[str, float] = {}
    for check in checks:
        if check.category not in PROJECTED or check.value is None or not check.tolerance:
            continue
        if check.id.endswith((".bubble", ".dew")) and check.value <= 0.0:
            continue
        ratios[check.id] = abs(check.value) / check.tolerance
    return ratios


def revision_projection(
    binding: RevisionBinding, document: Document, state: Mapping[str, float]
) -> tuple[Any, list[Any]]:
    """The verifier's projection of a revision-built `state` (spec §5.1) through the
    certificate's own helpers, and the table's checks at `state` itself (unprojected)."""
    from openflowsheet.models.revision_flowsheet import parse_revision
    from openflowsheet.thermo.syn001 import Syn001Provider
    from openflowsheet.verify.certificate import (
        BoundDeclaration,
        CheckPolicy,
        _project,
        _screen,
    )
    from openflowsheet.verify.checks import label_checks, residual_checks
    from openflowsheet.verify.table import revision_checks
    from openflowsheet.verify.zero_flow import dormant_outlets, zero_flow_splits

    policy = CheckPolicy()
    view = parse_revision(document)
    splits = lifted_splits(
        [(i.unit_id, i.model_id, i.wiring) for i in view.instances], view.components
    )
    target = BoundDeclaration(binding.spec, compile_problem(binding.spec), state)
    zero_flow = (*zero_flow_splits(view, splits, state), *dormant_outlets(view, state))
    rows, _ = residual_checks(
        target.compiled,
        target.spec,
        state,
        target.context,
        target.spec.row_kinds,
        policy.tolerances,
    )
    rows += label_checks(zero_flow, state, policy.tolerances)
    provider = Syn001Provider()
    projection = _project(
        target,
        state,
        rows,
        _screen(target, state, zero_flow),
        zero_flow=zero_flow,
        streams=view.streams,
        provider=provider,
        policy=policy,
    )
    unprojected = revision_checks(
        view,
        splits,
        state,
        provider=provider,
        context=target.context,
        tolerances=policy.tolerances,
    )
    return projection, unprojected
