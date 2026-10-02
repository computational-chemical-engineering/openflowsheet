"""Fable's closed-form reference generator for the T01 structural specification.

Everything here follows from the SYN-001 equations as *written* in ``docs/derivations/SYN-001.md``
§4 and the lifted two-phase form of ADR 0001 D2.5 (each row's variables transcribed by hand from
the equation statement, section 1 below), the process topology of plan §3.2, and the definitions
in ``docs/derivations/T01-structural-spec.md``. It imports nothing from ``process_runtime`` or
``benchmarks``: the structural facts it emits are the *expectations* the T01 analysis is judged
against, so they must not come from the compiler, the graph layer or the solver.

Every algorithm here is written from its definition, not taken from a library: a maximum matching
by augmenting paths, the lexicographically least maximum matching by forced assignment, the coarse
Dulmage-Mendelsohn partition by alternating reachability, strongly connected components by
Tarjan's algorithm, the canonical block order by the least-row-index topological rule, and the
affine-copy certificate by K03 §7.2's union-find pass on literal coefficients. They are small, and
being small is the point: the implementation is compared against a second, independent derivation
of the same objects, never against itself.

Run from the repository root inside the project environment::

    python docs/derivations/scripts/t01_reference.py --check
    python docs/derivations/scripts/t01_reference.py --emit benchmarks/t01/reference_values.yaml

``--check`` re-derives every identity the specification claims about its own numbers and refuses
to emit when one stops holding (T01-structural-spec §14.2). ``--emit`` is byte-reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import random
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# --------------------------------------------------------------------------------------------
# 1. The SYN-001 declaration, transcribed by hand from the equations
# --------------------------------------------------------------------------------------------

COMPONENTS = ("A", "B", "C")
STREAMS = ("S1", "S2", "S3", "S4", "S5", "S6", "S7")

#: ADR 0001 D6's registered tolerances by kind, for the affine-copy certificate (§8.2).
KIND_TOLERANCE = {"pressure": 1e-2, "temperature": 1e-6}


def flow(stream: str, c: str) -> str:
    return f"{stream}.n.{c}"


def temp(stream: str) -> str:
    return f"{stream}.T"


def pres(stream: str) -> str:
    return f"{stream}.P"


def ntp(stream: str) -> tuple[str, ...]:
    """The `nTP-v1` state variables of a material stream (ADR 0001 D2.1)."""
    return (*(flow(stream, c) for c in COMPONENTS), temp(stream), pres(stream))


#: `CompiledProblemMetadata.variable_ids` order: streams S1..S7 in nTP order, then the unit-owned
#: variables in unit assembly order (heater duty, heater lifted split, flash duty, flash totals).
VARIABLE_IDS: tuple[str, ...] = (
    *itertools.chain.from_iterable(ntp(s) for s in STREAMS),
    "U-HEAT.Q",
    *(f"S3.vap.{c}" for c in COMPONENTS),
    *(f"S3.liq.{c}" for c in COMPONENTS),
    "S3.V",
    "S3.L",
    "U-FLASH.Q",
    "S4.N",
    "S5.N",
)

VARIABLE_KINDS: dict[str, str] = {}
for _s in STREAMS:
    for _c in COMPONENTS:
        VARIABLE_KINDS[flow(_s, _c)] = "molar_flow"
    VARIABLE_KINDS[temp(_s)] = "temperature"
    VARIABLE_KINDS[pres(_s)] = "pressure"
VARIABLE_KINDS.update(
    {
        "U-HEAT.Q": "heat_rate",
        "U-FLASH.Q": "heat_rate",
        "S3.V": "molar_flow",
        "S3.L": "molar_flow",
        "S4.N": "molar_flow",
        "S5.N": "molar_flow",
    }
)
for _c in COMPONENTS:
    VARIABLE_KINDS[f"S3.vap.{_c}"] = "molar_flow"
    VARIABLE_KINDS[f"S3.liq.{_c}"] = "molar_flow"


@dataclass(frozen=True)
class Row:
    """One declared equation: its id, the unit that authors it, its kind, the variables it
    references and — when the row is affine with literal coefficients — those coefficients and
    its constant as signed parameter names, so that a certificate's mismatch is a function of
    parameters alone."""

    row_id: str
    unit: str
    kind: str
    columns: tuple[str, ...]
    #: `None` for a nonlinear row or a row whose coefficient is a parameter; else
    #: {column: literal coefficient}.
    affine: Mapping[str, int] | None = None
    #: Constant term as `(sign, parameter)` pairs: row = Σ coef·x + Σ sign·parameter.
    constant: tuple[tuple[int, str], ...] = ()
    #: The revision specification that pins this row's parameter, when the row is one.
    specification: str | None = None


def _rows() -> list[Row]:
    rows: list[Row] = []
    s1, s2, s3, s4, s5, s6, s7 = STREAMS
    # U-FEED: the fresh feed is fully specified (plan §3.1): n, T, P each pinned.
    for c in COMPONENTS:
        rows.append(
            Row(
                f"U-FEED:FEED-n:{c}",
                "U-FEED",
                "molar_flow",
                (flow(s1, c),),
                affine={flow(s1, c): +1},
                constant=((-1, f"U-FEED.n_spec.{c}"),),
                specification=f"SPEC-feed-n-{c}",
            )
        )
    rows.append(
        Row(
            "U-FEED:FEED-T",
            "U-FEED",
            "temperature",
            (temp(s1),),
            affine={temp(s1): +1},
            constant=((-1, "U-FEED.T_spec"),),
            specification="SPEC-feed-T",
        )
    )
    rows.append(
        Row(
            "U-FEED:FEED-P",
            "U-FEED",
            "pressure",
            (pres(s1),),
            affine={pres(s1): +1},
            constant=((-1, "U-FEED.P_spec"),),
            specification="SPEC-feed-P",
        )
    )
    # U-MIX (adiabatic): n_S2 = n_S1 + n_S6; H(S2) = H(S1) + H(S6); P_S2 = P_S1 = P_S6.
    for c in COMPONENTS:
        rows.append(
            Row(
                f"U-MIX:MIX-mole:{c}",
                "U-MIX",
                "molar_flow",
                (flow(s1, c), flow(s6, c), flow(s2, c)),
                affine={flow(s1, c): +1, flow(s6, c): +1, flow(s2, c): -1},
            )
        )
    rows.append(Row("U-MIX:MIX-energy", "U-MIX", "heat_rate", (*ntp(s1), *ntp(s6), *ntp(s2))))
    rows.append(
        Row(
            "U-MIX:MIX-pressure:0",
            "U-MIX",
            "pressure",
            (pres(s1), pres(s2)),
            affine={pres(s1): +1, pres(s2): -1},
        )
    )
    rows.append(
        Row(
            "U-MIX:MIX-pressure:1",
            "U-MIX",
            "pressure",
            (pres(s6), pres(s2)),
            affine={pres(s6): +1, pres(s2): -1},
        )
    )
    # U-HEAT (TP-state outlet, lifted split): n_S3 = n_S2; T_S3 = T_spec; P_S3 = P_S2 + dP;
    # Q_h = H(S3) - H(S2) with S3's enthalpy through the lifted split; the five lifting rows.
    for c in COMPONENTS:
        rows.append(
            Row(
                f"U-HEAT:HEAT-mole:{c}",
                "U-HEAT",
                "molar_flow",
                (flow(s2, c), flow(s3, c)),
                affine={flow(s2, c): +1, flow(s3, c): -1},
            )
        )
    rows.append(
        Row(
            "U-HEAT:HEAT-T",
            "U-HEAT",
            "temperature",
            (temp(s3),),
            affine={temp(s3): +1},
            constant=((-1, "U-HEAT.T_spec"),),
            specification="SPEC-heater-outlet-T",
        )
    )
    rows.append(
        Row(
            "U-HEAT:HEAT-pressure",
            "U-HEAT",
            "pressure",
            (pres(s3), pres(s2)),
            affine={pres(s3): +1, pres(s2): -1},
            constant=((-1, "U-HEAT.pressure_drop"),),
        )
    )
    lifted3 = (*(f"S3.vap.{c}" for c in COMPONENTS), *(f"S3.liq.{c}" for c in COMPONENTS))
    rows.append(
        Row(
            "U-HEAT:HEAT-duty",
            "U-HEAT",
            "heat_rate",
            (*ntp(s2), temp(s3), pres(s3), *lifted3, "U-HEAT.Q"),
        )
    )
    for c in COMPONENTS:
        rows.append(
            Row(
                f"U-HEAT:HEAT-equilibrium:{c}",
                "U-HEAT",
                "molar_flow_squared",
                (f"S3.vap.{c}", "S3.L", f"S3.liq.{c}", "S3.V", temp(s3), pres(s3)),
            )
        )
        rows.append(
            Row(
                f"U-HEAT:split:{c}",
                "U-HEAT",
                "molar_flow",
                (flow(s3, c), f"S3.vap.{c}", f"S3.liq.{c}"),
                affine={flow(s3, c): +1, f"S3.vap.{c}": -1, f"S3.liq.{c}": -1},
            )
        )
    rows.append(
        Row(
            "U-HEAT:Vdef",
            "U-HEAT",
            "molar_flow",
            ("S3.V", *(f"S3.vap.{c}" for c in COMPONENTS)),
            affine={"S3.V": +1, **{f"S3.vap.{c}": -1 for c in COMPONENTS}},
        )
    )
    rows.append(
        Row(
            "U-HEAT:Ldef",
            "U-HEAT",
            "molar_flow",
            ("S3.L", *(f"S3.liq.{c}" for c in COMPONENTS)),
            affine={"S3.L": +1, **{f"S3.liq.{c}": -1 for c in COMPONENTS}},
        )
    )
    # U-FLASH (isothermal, isobaric): n_S4 + n_S5 = n_S3; lifted equilibrium
    # n4_i N5 - K_i(T4, P4) n5_i N4 = 0; T_S4 = T_S5 = T_f; P_S4 = P_S5 = P_S3 = P_f;
    # Q_f = H(S4) + H(S5) - H(S3); N4 = Σ n4, N5 = Σ n5.
    for c in COMPONENTS:
        rows.append(
            Row(
                f"U-FLASH:FLASH-mole:{c}",
                "U-FLASH",
                "molar_flow",
                (flow(s3, c), flow(s4, c), flow(s5, c)),
                affine={flow(s3, c): +1, flow(s4, c): -1, flow(s5, c): -1},
            )
        )
        rows.append(
            Row(
                f"U-FLASH:FLASH-equilibrium:{c}",
                "U-FLASH",
                "molar_flow_squared",
                (flow(s4, c), "S5.N", flow(s5, c), "S4.N", temp(s4), pres(s4)),
            )
        )
    rows.append(
        Row(
            "U-FLASH:FLASH-T:vapor",
            "U-FLASH",
            "temperature",
            (temp(s4),),
            affine={temp(s4): +1},
            constant=((-1, "U-FLASH.T_spec"),),
            specification="SPEC-flash-T",
        )
    )
    rows.append(
        Row(
            "U-FLASH:FLASH-T:liquid",
            "U-FLASH",
            "temperature",
            (temp(s5),),
            affine={temp(s5): +1},
            constant=((-1, "U-FLASH.T_spec"),),
            specification="SPEC-flash-T",
        )
    )
    rows.append(
        Row(
            "U-FLASH:FLASH-P:vapor",
            "U-FLASH",
            "pressure",
            (pres(s4),),
            affine={pres(s4): +1},
            constant=((-1, "U-FLASH.P_spec"),),
            specification="SPEC-flash-P",
        )
    )
    rows.append(
        Row(
            "U-FLASH:FLASH-P:liquid",
            "U-FLASH",
            "pressure",
            (pres(s5),),
            affine={pres(s5): +1},
            constant=((-1, "U-FLASH.P_spec"),),
            specification="SPEC-flash-P",
        )
    )
    rows.append(
        Row(
            "U-FLASH:FLASH-P:inlet",
            "U-FLASH",
            "pressure",
            (pres(s3),),
            affine={pres(s3): +1},
            constant=((-1, "U-FLASH.P_spec"),),
            specification="SPEC-flash-P",
        )
    )
    rows.append(
        Row(
            "U-FLASH:FLASH-duty",
            "U-FLASH",
            "heat_rate",
            (temp(s3), pres(s3), *lifted3, *ntp(s4), *ntp(s5), "U-FLASH.Q"),
        )
    )
    rows.append(
        Row(
            "U-FLASH:Ndef:vapor",
            "U-FLASH",
            "molar_flow",
            ("S4.N", *(flow(s4, c) for c in COMPONENTS)),
            affine={"S4.N": +1, **{flow(s4, c): -1 for c in COMPONENTS}},
        )
    )
    rows.append(
        Row(
            "U-FLASH:Ndef:liquid",
            "U-FLASH",
            "molar_flow",
            ("S5.N", *(flow(s5, c) for c in COMPONENTS)),
            affine={"S5.N": +1, **{flow(s5, c): -1 for c in COMPONENTS}},
        )
    )
    # U-SPLIT: n_S6 = r n_S5; n_S7 = (1-r) n_S5; T and P copied. The flow rows carry the
    # parameter `r` as a coefficient: affine, but not literal ±1, so never copy rows.
    for c in COMPONENTS:
        rows.append(
            Row(f"U-SPLIT:SPLIT-recycle:{c}", "U-SPLIT", "molar_flow", (flow(s6, c), flow(s5, c)))
        )
        rows.append(
            Row(f"U-SPLIT:SPLIT-purge:{c}", "U-SPLIT", "molar_flow", (flow(s7, c), flow(s5, c)))
        )
    rows.append(
        Row(
            "U-SPLIT:SPLIT-T:recycle",
            "U-SPLIT",
            "temperature",
            (temp(s6), temp(s5)),
            affine={temp(s6): +1, temp(s5): -1},
        )
    )
    rows.append(
        Row(
            "U-SPLIT:SPLIT-T:purge",
            "U-SPLIT",
            "temperature",
            (temp(s7), temp(s5)),
            affine={temp(s7): +1, temp(s5): -1},
        )
    )
    rows.append(
        Row(
            "U-SPLIT:SPLIT-P:recycle",
            "U-SPLIT",
            "pressure",
            (pres(s6), pres(s5)),
            affine={pres(s6): +1, pres(s5): -1},
        )
    )
    rows.append(
        Row(
            "U-SPLIT:SPLIT-P:purge",
            "U-SPLIT",
            "pressure",
            (pres(s7), pres(s5)),
            affine={pres(s7): +1, pres(s5): -1},
        )
    )
    return rows


#: The K02 assembly order of the 49 rows (`CompiledProblemMetadata.equation_ids`): unit by unit,
#: and within a unit in the order the unit authors its rows. Stated explicitly so that the
#: transcription is checked against it rather than trusted.
EQUATION_ORDER: tuple[str, ...] = (
    "U-FEED:FEED-n:A",
    "U-FEED:FEED-n:B",
    "U-FEED:FEED-n:C",
    "U-FEED:FEED-T",
    "U-FEED:FEED-P",
    "U-MIX:MIX-mole:A",
    "U-MIX:MIX-mole:B",
    "U-MIX:MIX-mole:C",
    "U-MIX:MIX-energy",
    "U-MIX:MIX-pressure:0",
    "U-MIX:MIX-pressure:1",
    "U-HEAT:HEAT-mole:A",
    "U-HEAT:HEAT-mole:B",
    "U-HEAT:HEAT-mole:C",
    "U-HEAT:HEAT-T",
    "U-HEAT:HEAT-pressure",
    "U-HEAT:HEAT-duty",
    "U-HEAT:HEAT-equilibrium:A",
    "U-HEAT:split:A",
    "U-HEAT:HEAT-equilibrium:B",
    "U-HEAT:split:B",
    "U-HEAT:HEAT-equilibrium:C",
    "U-HEAT:split:C",
    "U-HEAT:Vdef",
    "U-HEAT:Ldef",
    "U-FLASH:FLASH-mole:A",
    "U-FLASH:FLASH-equilibrium:A",
    "U-FLASH:FLASH-mole:B",
    "U-FLASH:FLASH-equilibrium:B",
    "U-FLASH:FLASH-mole:C",
    "U-FLASH:FLASH-equilibrium:C",
    "U-FLASH:FLASH-T:vapor",
    "U-FLASH:FLASH-T:liquid",
    "U-FLASH:FLASH-P:vapor",
    "U-FLASH:FLASH-P:liquid",
    "U-FLASH:FLASH-P:inlet",
    "U-FLASH:FLASH-duty",
    "U-FLASH:Ndef:vapor",
    "U-FLASH:Ndef:liquid",
    "U-SPLIT:SPLIT-recycle:A",
    "U-SPLIT:SPLIT-purge:A",
    "U-SPLIT:SPLIT-recycle:B",
    "U-SPLIT:SPLIT-purge:B",
    "U-SPLIT:SPLIT-recycle:C",
    "U-SPLIT:SPLIT-purge:C",
    "U-SPLIT:SPLIT-T:recycle",
    "U-SPLIT:SPLIT-T:purge",
    "U-SPLIT:SPLIT-P:recycle",
    "U-SPLIT:SPLIT-P:purge",
)

#: The pinned parameters (benchmarks/syn001/cases/*.yaml), nominal values. Certificate
#: mismatches are functions of these alone.
PARAMETERS_NOMINAL: dict[str, float] = {
    "U-FEED.n_spec.A": 1.0,
    "U-FEED.n_spec.B": 1.0,
    "U-FEED.n_spec.C": 1.0,
    "U-FEED.T_spec": 300.0,
    "U-FEED.P_spec": 100_000.0,
    "U-HEAT.T_spec": 350.0,
    "U-HEAT.pressure_drop": 0.0,
    "U-FLASH.T_spec": 360.0,
    "U-FLASH.P_spec": 100_000.0,
    "U-SPLIT.split_fraction": 0.5,
}
VARIANT_PARAMETERS: dict[str, dict[str, float]] = {
    "SYN-001-nominal": PARAMETERS_NOMINAL,
    "SYN-001-once-through": {**PARAMETERS_NOMINAL, "U-SPLIT.split_fraction": 0.0},
    "SYN-001-high-recycle": {**PARAMETERS_NOMINAL, "U-SPLIT.split_fraction": 0.95},
    "SYN-001-all-liquid-310K": {**PARAMETERS_NOMINAL, "U-FLASH.T_spec": 310.0},
    "SYN-001-all-vapor-420K": {**PARAMETERS_NOMINAL, "U-FLASH.T_spec": 420.0},
}

#: The conflicting revision adds one specification-promotion row over the heater duty column
#: (T01 spec §5.4): id `SPEC:<specification id>`, attributed to the unit that owns the column.
CONFLICTING_ROW = Row(
    "SPEC:SPEC-heater-duty",
    "U-HEAT",
    "heat_rate",
    ("U-HEAT.Q",),
    affine={"U-HEAT.Q": +1},
    constant=((-1, "SPEC-heater-duty.value"),),
    specification="SPEC-heater-duty",
)

#: Process multigraph of plan §3.2: material connections (stream, producer, consumer), in the
#: revision's connection order.
CONNECTIONS: tuple[tuple[str, str, str], ...] = (
    ("S1", "U-FEED", "U-MIX"),
    ("S2", "U-MIX", "U-HEAT"),
    ("S3", "U-HEAT", "U-FLASH"),
    ("S4", "U-FLASH", "U-PRODUCT"),
    ("S5", "U-FLASH", "U-SPLIT"),
    ("S6", "U-SPLIT", "U-MIX"),
    ("S7", "U-SPLIT", "U-PURGE"),
)
#: Units with no material inlet: their outlet state is fixed by specification (§9.2).
BOUNDARY_UNITS = ("U-FEED",)
#: Units that lift a two-phase split, i.e. select a phase regime (K03 §9.1).
PHASE_SELECTING_UNITS = ("U-HEAT", "U-FLASH")

#: *Measured* on `main` at f603e9b (probe of 2026-09-23, see T01 spec §3.4 and §12); recorded
#: to argue assertions, never as expectations. The backend pattern is the CasADi sparsity after
#: constant folding of the pinned parameters; at r = 0 the three `SPLIT-recycle:i × S5.n.i`
#: entries fold away. The zero counts are numerically-zero declared entries at each variant's
#: registered initializer state.
MEASURED: dict[str, Any] = {
    "backend_pattern_nnz": {
        "SYN-001-nominal": 170,
        "SYN-001-once-through": 167,
        "SYN-001-high-recycle": 170,
        "SYN-001-all-liquid-310K": 170,
        "SYN-001-all-vapor-420K": 170,
        "SYN-001-conflicting-heater-spec": 171,
    },
    "backend_entries_absent_at_r0": [
        ["U-SPLIT:SPLIT-recycle:A", "S5.n.A"],
        ["U-SPLIT:SPLIT-recycle:B", "S5.n.B"],
        ["U-SPLIT:SPLIT-recycle:C", "S5.n.C"],
    ],
    "numerically_zero_declared_entries_at_initializer_state": {
        "SYN-001-nominal": 4,
        "SYN-001-once-through": 12,
        "SYN-001-high-recycle": 16,
        "SYN-001-all-liquid-310K": 17,
        "SYN-001-all-vapor-420K": 26,
    },
    "nominal_zero_entries": [
        ["U-MIX:MIX-energy", "S1.n.A"],
        ["U-MIX:MIX-energy", "S1.n.B"],
        ["U-MIX:MIX-energy", "S1.n.C"],
        ["U-FLASH:FLASH-duty", "S4.P"],
    ],
    "scipy_hopcroft_karp_unmatched_rows_nominal": [
        "U-FLASH:FLASH-P:inlet",
        "U-SPLIT:SPLIT-P:recycle",
    ],
    "k03_solve_plan_inner_block": [44, 44],
    "k03_constant_mismatch_floor_pa": 1e-11,
}


# --------------------------------------------------------------------------------------------
# 2. Structural algorithms, from their definitions
# --------------------------------------------------------------------------------------------


@dataclass
class Incidence:
    rows: tuple[str, ...]
    cols: tuple[str, ...]
    adj: dict[str, tuple[str, ...]]  # row -> columns, kept in column declaration order

    def __post_init__(self) -> None:
        cidx = {c: i for i, c in enumerate(self.cols)}
        if len(cidx) != len(self.cols) or len(set(self.rows)) != len(self.rows):
            raise ValueError("duplicate ids")
        for r in self.rows:
            for c in self.adj[r]:
                if c not in cidx:
                    raise ValueError(f"row {r} references undeclared column {c}")
        self.adj = {r: tuple(sorted(self.adj[r], key=cidx.__getitem__)) for r in self.rows}

    @property
    def nnz(self) -> int:
        return sum(len(v) for v in self.adj.values())

    def restrict(self, rows: Iterable[str], cols: Iterable[str]) -> Incidence:
        cset = set(cols)
        rset = set(rows)
        cols_t = tuple(c for c in self.cols if c in cset)
        rows_t = tuple(r for r in self.rows if r in rset)
        return Incidence(
            rows_t, cols_t, {r: tuple(c for c in self.adj[r] if c in cset) for r in rows_t}
        )

    def col_adj(self) -> dict[str, tuple[str, ...]]:
        out: dict[str, list[str]] = {c: [] for c in self.cols}
        for r in self.rows:
            for c in self.adj[r]:
                out[c].append(r)
        return {c: tuple(v) for c, v in out.items()}


def maximum_matching(inc: Incidence, forced: Mapping[str, str] | None = None) -> dict[str, str]:
    """A maximum matching (column -> row) by augmenting paths in declaration order, with some
    columns optionally forced to given rows (kept fixed; the rest is maximized)."""
    forced = dict(forced or {})
    row_of: dict[str, str] = dict(forced)
    col_of: dict[str, str] = {r: c for c, r in forced.items()}
    col_adj = inc.col_adj()

    def augment(c: str, seen: set[str]) -> bool:
        for r in col_adj[c]:
            if r in seen or (r in col_of and col_of[r] in forced):
                continue
            seen.add(r)
            if r not in col_of or augment(col_of[r], seen):
                col_of[r] = c
                row_of[c] = r
                return True
        return False

    for c in inc.cols:
        if c not in row_of:
            augment(c, set())
    return row_of


def canonical_matching(inc: Incidence) -> dict[str, str]:
    """The lexicographically least maximum matching (T01 spec §6.2): columns in declaration
    order, each assigned the least row (declaration order) that still admits a maximum matching,
    or left unmatched when no row does. Unique by construction: a minimum of a finite set."""
    size = len(maximum_matching(inc))
    col_adj = inc.col_adj()
    forced: dict[str, str] = {}
    for c in inc.cols:
        taken = set(forced.values())
        for r in col_adj[c]:
            if r in taken:
                continue
            if len(maximum_matching(inc, {**forced, c: r})) == size:
                forced[c] = r
                break
    assert len(forced) == size
    return forced


def dulmage_mendelsohn(inc: Incidence, matching: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Coarse DM partition from any maximum matching (T01 spec §6.3; matching-independent).

    Over-determined part: the unmatched rows plus everything reachable from them by alternating
    paths (row -> any of its columns -> that column's matched row). Under-determined part: the
    unmatched columns plus everything reachable (column -> any of its rows -> that row's matched
    column). The square part is the rest."""
    row_of = dict(matching)
    col_of = {r: c for c, r in row_of.items()}
    col_adj = inc.col_adj()

    over_rows: set[str] = {r for r in inc.rows if r not in col_of}
    over_cols: set[str] = set()
    stack = list(over_rows)
    while stack:
        r = stack.pop()
        for c in inc.adj[r]:
            if c in over_cols:
                continue
            over_cols.add(c)
            m = row_of.get(c)
            if m is not None and m not in over_rows:
                over_rows.add(m)
                stack.append(m)

    under_cols: set[str] = {c for c in inc.cols if c not in row_of}
    under_rows: set[str] = set()
    stack = list(under_cols)
    while stack:
        c = stack.pop()
        for r in col_adj[c]:
            if r in under_rows:
                continue
            under_rows.add(r)
            m = col_of.get(r)
            if m is not None and m not in under_cols:
                under_cols.add(m)
                stack.append(m)

    if over_rows & under_rows or over_cols & under_cols:
        raise AssertionError("over- and under-determined parts overlap: not a maximum matching")
    return {
        "over_rows": tuple(r for r in inc.rows if r in over_rows),
        "over_cols": tuple(c for c in inc.cols if c in over_cols),
        "under_rows": tuple(r for r in inc.rows if r in under_rows),
        "under_cols": tuple(c for c in inc.cols if c in under_cols),
        "square_rows": tuple(r for r in inc.rows if r not in over_rows and r not in under_rows),
        "square_cols": tuple(c for c in inc.cols if c not in over_cols and c not in under_cols),
    }


def strongly_connected_components(
    nodes: Sequence[str], edges: Mapping[str, Iterable[str]]
) -> list[tuple[str, ...]]:
    """Tarjan's algorithm, iterative; each component's members in node declaration order."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on: set[str] = set()
    stack: list[str] = []
    comps: list[tuple[str, ...]] = []
    order = {n: i for i, n in enumerate(nodes)}
    counter = 0
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(edges.get(root, ())))]
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on.add(root)
        while work:
            v, it = work[-1]
            advanced = False
            for w in it:
                if w not in index:
                    index[w] = low[w] = counter
                    counter += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(edges.get(w, ()))))
                    advanced = True
                    break
                if w in on:
                    low[v] = min(low[v], index[w])
            if advanced:
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                comps.append(tuple(sorted(comp, key=order.__getitem__)))
    return comps


def block_triangular_form(inc: Incidence, matching: Mapping[str, str]) -> list[dict[str, Any]]:
    """Fine decomposition of a square, perfectly matched incidence (T01 spec §7): the SCCs of
    the dependency digraph (row r depends on the rows matched to r's other columns), in the
    canonical block order — a topological order of the condensation in which, among the blocks
    whose predecessors are all placed, the one whose first row has the least declaration index
    comes first. Each block lists its rows and columns in declaration order."""
    row_of = dict(matching)
    col_of = {r: c for c, r in row_of.items()}
    if (
        set(col_of) != set(inc.rows)
        or set(row_of) != set(inc.cols)
        or len(inc.rows) != len(inc.cols)
    ):
        raise ValueError("block_triangular_form needs a square, perfectly matched incidence")
    deps: dict[str, list[str]] = {r: [] for r in inc.rows}
    for r in inc.rows:
        for c in inc.adj[r]:
            r2 = row_of[c]
            if r2 != r:
                deps[r].append(r2)
    comps = strongly_connected_components(inc.rows, deps)
    comp_of = {r: k for k, comp in enumerate(comps) for r in comp}
    ridx = {r: i for i, r in enumerate(inc.rows)}
    preds: dict[int, set[int]] = {k: set() for k in range(len(comps))}
    for r, rs in deps.items():
        for r2 in rs:
            if comp_of[r2] != comp_of[r]:
                preds[comp_of[r]].add(comp_of[r2])
    placed: list[int] = []
    remaining = set(range(len(comps)))
    while remaining:
        ready = [k for k in remaining if preds[k] <= set(placed)]
        if not ready:
            raise AssertionError("condensation is not acyclic")
        k = min(ready, key=lambda k: ridx[comps[k][0]])
        placed.append(k)
        remaining.discard(k)
    blocks = []
    for k in placed:
        rows = comps[k]
        cols = tuple(sorted((col_of[r] for r in rows), key=inc.cols.index))
        blocks.append(
            {
                "rows": rows,
                "cols": cols,
                "size": len(rows),
                "depends_on": tuple(sorted(placed.index(j) for j in preds[k])),
            }
        )
    return blocks


# --------------------------------------------------------------------------------------------
# 3. The certificate class: affine ±1 copy rows closing a cycle (K03 §7.2, on the declaration)
# --------------------------------------------------------------------------------------------

CONST = "<const>"


def affine_copy_certificates(
    rows: Sequence[Row], parameters: Mapping[str, float]
) -> dict[str, Any]:
    """K03 §7.2's union-find pass in declaration order, on the declaration's literal coefficients,
    with each mismatch computed from parameters alone (T01 spec §8.2). Rows of a certifiable kind
    that are affine but outside the two-node ±1 class are reported `uncertified_affine_rows`."""
    parent: dict[str, str] = {}
    edges: dict[str, list[tuple[str, str, int]]] = {}

    def find(n: str) -> str:
        parent.setdefault(n, n)
        edges.setdefault(n, [])
        while parent[n] != n:
            n = parent[n]
        return n

    def path(a: str, b: str) -> tuple[tuple[str, int], ...]:
        stack = [(a, ())]
        seen = {a}
        while stack:
            n, taken = stack.pop()
            if n == b:
                return taken
            for nb, rid, sign in edges[n]:
                if nb not in seen:
                    seen.add(nb)
                    stack.append((nb, (*taken, (rid, sign))))
        raise AssertionError("connected but no path")

    constant_of: dict[str, float] = {}
    eliminated: list[dict[str, Any]] = []
    retained: list[str] = []
    uncertified: list[str] = []
    for row in rows:
        if row.affine is None or row.kind not in KIND_TOLERANCE:
            retained.append(row.row_id)
            continue
        if {VARIABLE_KINDS.get(c, row.kind) for c in row.affine} != {row.kind}:
            retained.append(row.row_id)
            continue
        if any(abs(v) != 1 for v in row.affine.values()) or len(row.affine) > 2:
            uncertified.append(row.row_id)
            retained.append(row.row_id)
            continue
        # A copy is a *difference*. `P1 + P2 - s` has two `+1` coefficients and would otherwise
        # take `P1` as its positive node and CONST as its negative, certifying it as `P1 - s`, an
        # identity false at every state. Amended on 2026-09-23 per must-fix M4 of the T01 review,
        # which found the same defect in this generator, in section 8.2 of the specification and
        # in the implementation. No registered value changes: SYN-001 declares no such row.
        if len(row.affine) == 2 and sum(row.affine.values()) != 0:
            uncertified.append(row.row_id)
            retained.append(row.row_id)
            continue
        constant_of[row.row_id] = sum(s * parameters[p] for s, p in row.constant)
        pos = next((c for c, v in row.affine.items() if v > 0), CONST)
        neg = next((c for c, v in row.affine.items() if v < 0), CONST)
        find(pos)
        find(neg)
        if find(pos) == find(neg):
            p = path(pos, neg)
            m = constant_of[row.row_id] - sum(s * constant_of[rid] for rid, s in p)
            eliminated.append(
                {
                    "row_id": row.row_id,
                    "equals": [[rid, s] for rid, s in p],
                    "constant_mismatch": m,
                    "tolerance": KIND_TOLERANCE[row.kind],
                    "kind": row.kind,
                    "consistent": abs(m) <= KIND_TOLERANCE[row.kind],
                }
            )
        else:
            edges[pos].append((neg, row.row_id, +1))
            edges[neg].append((pos, row.row_id, -1))
            parent[find(pos)] = find(neg)
            retained.append(row.row_id)
    return {"eliminated": eliminated, "retained": retained, "uncertified_affine_rows": uncertified}


# --------------------------------------------------------------------------------------------
# 4. The analysis, end to end, as the specification defines it
# --------------------------------------------------------------------------------------------


def incidence_of(rows: Sequence[Row], cols: Sequence[str] = VARIABLE_IDS) -> Incidence:
    return Incidence(
        tuple(r.row_id for r in rows), tuple(cols), {r.row_id: r.columns for r in rows}
    )


def stream_of(col: str) -> str | None:
    """The stream whose nTP state a column belongs to; lifted variables belong to none (§9.3)."""
    s, _, rest = col.partition(".")
    if s in STREAMS and (rest in ("T", "P") or rest.startswith("n.")):
        return s
    return None


def unit_columns(unit: str, cols: Sequence[str]) -> tuple[str, ...]:
    """A column belongs to the unit that produces its stream, or to the unit its id names (§8.3)."""
    produced = {s for s, a, _ in CONNECTIONS if a == unit}
    return tuple(c for c in cols if c.split(".")[0] in produced or c.startswith(unit + "."))


def unit_degrees_of_freedom(
    rows: Sequence[Row], certified: Sequence[str], cols: Sequence[str] = VARIABLE_IDS
) -> dict[str, Any]:
    """T01 spec §8.3: per unit, with every inlet treated as known and certified rows removed,
    `dof = |C_u| - structural rank of the unit's model rows over C_u`; `specifications` = the
    specification rows targeting C_u; `over_specified` iff specifications > dof."""
    units: list[str] = []
    for _, a, b in CONNECTIONS:
        for u in (a, b):
            if u not in units:
                units.append(u)
    out = {}
    for u in units:
        cu = unit_columns(u, cols)
        cu_set = set(cu)
        model = [
            r
            for r in rows
            if r.unit == u
            and r.specification is None
            and r.row_id not in certified
            and set(r.columns) & cu_set
        ]
        specs = [
            r
            for r in rows
            if r.specification is not None and r.row_id not in certified and set(r.columns) & cu_set
        ]
        inc = Incidence(
            tuple(r.row_id for r in model),
            cu,
            {r.row_id: tuple(c for c in r.columns if c in cu_set) for r in model},
        )
        m = canonical_matching(inc)
        dm = dulmage_mendelsohn(inc, m)
        out[u] = {
            "columns": len(cu),
            "model_rows": len(model),
            "model_rank": len(m),
            "dof": len(cu) - len(m),
            "specifications": [r.specification for r in specs],
            "specification_rows": [r.row_id for r in specs],
            "over_specified": len(specs) > len(cu) - len(m),
            "local_excess_rows": list(dm["over_rows"]),
        }
    return out


def analyse(rows: Sequence[Row], parameters: Mapping[str, float], *, label: str) -> dict[str, Any]:
    inc = incidence_of(rows)
    matching = canonical_matching(inc)
    dm = dulmage_mendelsohn(inc, matching)
    cert = affine_copy_certificates(rows, parameters)
    certified = [e["row_id"] for e in cert["eliminated"] if e["consistent"]]
    conflicting = [e["row_id"] for e in cert["eliminated"] if not e["consistent"]]
    inc2 = inc.restrict([r for r in inc.rows if r not in certified], inc.cols)
    matching2 = canonical_matching(inc2)
    dm2 = dulmage_mendelsohn(inc2, matching2)
    row_by_id = {r.row_id: r for r in rows}
    if conflicting:
        finding = "SPECIFICATION_CONFLICT"
    elif dm2["under_cols"]:
        finding = "STRUCTURAL_UNDER_SPECIFICATION"
    elif dm2["over_rows"]:
        finding = "STRUCTURAL_OVER_SPECIFICATION"
    else:
        finding = "STRUCTURALLY_CLOSED"
    unit_dof = unit_degrees_of_freedom(rows, certified)
    over_units = [u for u, d in unit_dof.items() if d["over_specified"]]
    result: dict[str, Any] = {
        "label": label,
        "structural_counts": {
            "free_variables": len(inc.cols),
            "equations": len(inc.rows),
            "matched": len(matching),
            "unmatched": (len(inc.rows) - len(matching)) + (len(inc.cols) - len(matching)),
        },
        "nnz": inc.nnz,
        "canonical_matching": {c: matching[c] for c in inc.cols if c in matching},
        "unmatched_rows_canonical": [r for r in inc.rows if r not in matching.values()],
        "dm_full": {k: list(v) for k, v in dm.items()},
        "certificates": cert,
        "certified_rows": certified,
        "conflicting_rows": conflicting,
        "dm_after_certificates": {k: list(v) for k, v in dm2.items()},
        "excess": len(dm2["over_rows"]) - len(dm2["over_cols"]),
        "deficit": len(dm2["under_cols"]) - len(dm2["under_rows"]),
        "candidate_specification_rows": [r for r in dm2["over_rows"] if row_by_id[r].specification],
        "candidate_specifications": sorted(
            {row_by_id[r].specification for r in dm2["over_rows"] if row_by_id[r].specification}
        ),
        "finding": finding,
        "unit_dof": unit_dof,
        "over_specified_units": over_units,
        "implicated_objects": sorted(
            {*(s for u in over_units for s in unit_dof[u]["specifications"]), *over_units}
        ),
    }
    if finding == "STRUCTURALLY_CLOSED":
        blocks = block_triangular_form(inc2, matching2)
        result["btf_square"] = blocks
        result["block_sizes_sorted"] = sorted((b["size"] for b in blocks), reverse=True)
        result["largest_block_fraction"] = max(b["size"] for b in blocks) / len(inc2.rows)
        result["tear"] = tear_candidates(rows, inc2, matching2, blocks)
    return result


def _units_in_connection_order() -> list[str]:
    units: list[str] = []
    for _, a, b in CONNECTIONS:
        for u in (a, b):
            if u not in units:
                units.append(u)
    return units


def boundary_distances() -> dict[str, int | None]:
    """BFS distance from a boundary unit along material connections (§9.4)."""
    units = _units_in_connection_order()
    dist: dict[str, int | None] = {u: None for u in units}
    frontier = list(BOUNDARY_UNITS)
    for u in frontier:
        dist[u] = 0
    while frontier:
        nxt = []
        for u in frontier:
            for _, a, b in CONNECTIONS:
                if a == u and dist[b] is None:
                    dist[b] = dist[u] + 1  # type: ignore[operator]
                    nxt.append(b)
        frontier = nxt
    return dist


def tear_candidates(
    rows: Sequence[Row],
    sq: Incidence,
    matching: Mapping[str, str],
    blocks: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """T01 spec §9: process-graph loops; for each, every single connection whose removal breaks
    it; dimension = the stream's nTP variables inside a non-trivial block of the square BTF;
    least dimension, then least consumer boundary distance, then connection declaration order."""
    units = _units_in_connection_order()
    out_edges: dict[str, list[str]] = {u: [] for u in units}
    for _, a, b in CONNECTIONS:
        out_edges[a].append(b)
    loops = [c for c in strongly_connected_components(units, out_edges) if len(c) > 1]
    col_block = {c: k for k, b in enumerate(blocks) for c in b["cols"]}
    dist = boundary_distances()
    row_by_id = {r.row_id: r for r in rows}
    result: dict[str, Any] = {"process_loops": [list(loop) for loop in loops], "loops": []}
    for loop in loops:
        loop_set = set(loop)
        cycle_edges = [(s, a, b) for s, a, b in CONNECTIONS if a in loop_set and b in loop_set]
        candidates = []
        for s, a, b in cycle_edges:
            oe = {u: [v for s2, u2, v in CONNECTIONS if u2 == u and s2 != s] for u in units}
            breaks = not any(
                len(c) > 1 and set(c) & loop_set for c in strongly_connected_components(units, oe)
            )
            svars = [c for c in sq.cols if stream_of(c) == s]
            torn = [c for c in svars if blocks[col_block[c]]["size"] > 1]
            candidates.append(
                {
                    "stream": s,
                    "producer": a,
                    "consumer": b,
                    "breaks_loop": breaks,
                    "dimension": len(torn),
                    "torn_variables": torn,
                    "not_torn": [c for c in svars if c not in torn],
                    "consumer_boundary_distance": dist[b],
                }
            )
        feasible = [c for c in candidates if c["breaks_loop"]]
        best_dim = min(c["dimension"] for c in feasible)
        by_dim = [c for c in feasible if c["dimension"] == best_dim]
        best_dist = min(c["consumer_boundary_distance"] for c in by_dim)
        by_dist = [c for c in by_dim if c["consumer_boundary_distance"] == best_dist]
        chosen = by_dist[0]
        tear_vars = chosen["torn_variables"]
        tear_rows = [
            r
            for r in sq.rows
            if row_by_id[r].unit == chosen["producer"]
            and set(row_by_id[r].columns) & set(tear_vars)
        ]
        inner = sq.restrict(
            [r for r in sq.rows if r not in tear_rows], [c for c in sq.cols if c not in tear_vars]
        )
        m_inner = canonical_matching(inner)
        dm_inner = dulmage_mendelsohn(inner, m_inner)
        closed = not dm_inner["over_rows"] and not dm_inner["under_cols"]
        inner_blocks = block_triangular_form(inner, m_inner) if closed else None
        signature = None
        if inner_blocks is not None:
            blk_of_row = {r: k for k, b in enumerate(inner_blocks) for r in b["rows"]}
            start = {
                blk_of_row[m_inner[c]]
                for tr in tear_rows
                for c in row_by_id[tr].columns
                if c in m_inner
            }
            anc: set[int] = set()
            stack = list(start)
            while stack:
                k = stack.pop()
                if k in anc:
                    continue
                anc.add(k)
                stack.extend(inner_blocks[k]["depends_on"])
            phase = []
            for u in PHASE_SELECTING_UNITS:
                lifted = [
                    k
                    for k, b in enumerate(inner_blocks)
                    if b["size"] > 1 and all(row_by_id[r].unit == u for r in b["rows"])
                ]
                phase.append(
                    {
                        "unit": u,
                        "lifted_blocks": lifted,
                        "upstream_of_tear": any(k in anc for k in lifted),
                    }
                )
            signature = {
                "ancestor_blocks_of_tear_rows": sorted(anc),
                "phase_selecting": phase,
                "signature_units": [p["unit"] for p in phase if p["upstream_of_tear"]],
            }
        result["loops"].append(
            {
                "units": list(loop),
                "cycle_edges": [s for s, _, _ in cycle_edges],
                "candidates": candidates,
                "chosen_stream": chosen["stream"],
                "tie_break_used": "dimension"
                if len(by_dim) == 1
                else ("boundary_distance" if len(by_dist) == 1 else "declaration_order"),
                "tear_variables": tear_vars,
                "tear_rows": tear_rows,
                "inner_rows": len(inner.rows),
                "inner_cols": len(inner.cols),
                "inner_closed": closed,
                "inner_block_sizes": [b["size"] for b in inner_blocks] if inner_blocks else None,
                "inner_blocks": inner_blocks,
                "signature": signature,
            }
        )
    return result


# --------------------------------------------------------------------------------------------
# 5. Synthetic fixtures (closed-form structure, no flowsheet)
# --------------------------------------------------------------------------------------------


def synthetic_fixtures() -> dict[str, Any]:
    out: dict[str, Any] = {}

    def entry(inc: Incidence, **extra: Any) -> dict[str, Any]:
        m = canonical_matching(inc)
        dm = dulmage_mendelsohn(inc, m)
        return {
            "rows": list(inc.rows),
            "cols": list(inc.cols),
            "incidence": {r: list(cs) for r, cs in inc.adj.items()},
            "structural_rank": len(m),
            "canonical_matching": m,
            "dm": {k: list(v) for k, v in dm.items()},
            "structural_counts": {
                "free_variables": len(inc.cols),
                "equations": len(inc.rows),
                "matched": len(m),
                "unmatched": (len(inc.rows) - len(m)) + (len(inc.cols) - len(m)),
            },
            **extra,
        }

    # SQ-1: square (3x3) yet structurally singular — the plan's "square structural defect".
    out["SQ-1"] = entry(
        Incidence(
            ("r1", "r2", "r3"),
            ("x1", "x2", "x3"),
            {"r1": ("x1",), "r2": ("x1",), "r3": ("x2", "x3")},
        ),
        finding="STRUCTURAL_UNDER_SPECIFICATION",
        also_over=True,
        why="equations == variables, no perfect matching: a count-based validator passes it",
    )
    # SQ-2: perfectly matched, numerically dependent (x1 + x2 = 1; 2x1 + 2x2 = 2): T01 says nothing.
    out["SQ-2"] = entry(
        Incidence(("r1", "r2"), ("x1", "x2"), {"r1": ("x1", "x2"), "r2": ("x1", "x2")}),
        finding="STRUCTURALLY_CLOSED",
        numerical_matrix=[[1, 1], [2, 2]],
        why="structurally closed and numerically singular: the rank verdict is K04 [A08]'s",
    )
    # UND-1: two rows over three columns.
    out["UND-1"] = entry(
        Incidence(("r1", "r2"), ("x1", "x2", "x3"), {"r1": ("x1", "x2"), "r2": ("x2", "x3")}),
        finding="STRUCTURAL_UNDER_SPECIFICATION",
    )
    # OVR-1: a duplicated single-column specification — the smallest uncertified over-determination.
    out["OVR-1"] = entry(
        Incidence(
            ("r1", "r2", "r3"), ("x1", "x2"), {"r1": ("x1",), "r2": ("x1",), "r3": ("x1", "x2")}
        ),
        finding="STRUCTURAL_OVER_SPECIFICATION",
        why="a 2x1 over-determined block: small, and a genuine over-specification; a size"
        " threshold would pass it",
    )
    # TIE-1: the canonical matching is not what greedy-by-row gives.
    out["TIE-1"] = entry(
        Incidence(("r1", "r2"), ("x1", "x2"), {"r1": ("x1", "x2"), "r2": ("x1",)}),
        greedy_by_row_would_give={"x1": "r1", "x2": None},
    )
    # BTF-1: the canonical block order with a genuine topological tie.
    inc = Incidence(
        ("a", "b", "c", "d"),
        ("xa", "xb", "xc", "xd"),
        {"a": ("xa",), "b": ("xb",), "c": ("xa", "xb", "xc"), "d": ("xd",)},
    )
    m = canonical_matching(inc)
    out["BTF-1"] = {
        "rows": list(inc.rows),
        "cols": list(inc.cols),
        "incidence": {r: list(cs) for r, cs in inc.adj.items()},
        "block_order": [list(b["rows"]) for b in block_triangular_form(inc, m)],
        "why": "d has no predecessor but a larger row index than c; a plain Kahn queue"
        " would place d third",
    }
    # UNC-1: an affine ±1 pressure row over three columns closing a cycle: outside the certified
    # class, so retained and reported, never silently certified and never silently dropped.
    unc_rows = [
        Row(
            "p1",
            "U",
            "pressure",
            ("P1",),
            affine={"P1": +1},
            constant=((-1, "P_spec"),),
            specification="S-P1",
        ),
        Row("p2", "U", "pressure", ("P2", "P1"), affine={"P2": +1, "P1": -1}),
        Row("p3", "U", "pressure", ("P3", "P2"), affine={"P3": +1, "P2": -1}),
        Row("p4", "U", "pressure", ("P1", "P2", "P3"), affine={"P1": +1, "P2": +1, "P3": -1}),
    ]
    cert = affine_copy_certificates(unc_rows, {"P_spec": 1.0e5})
    out["UNC-1"] = {
        "rows": [r.row_id for r in unc_rows],
        "cols": ["P1", "P2", "P3"],
        "incidence": {r.row_id: list(r.columns) for r in unc_rows},
        "certified": [e["row_id"] for e in cert["eliminated"]],
        "uncertified_affine_rows": cert["uncertified_affine_rows"],
        "finding": "STRUCTURAL_OVER_SPECIFICATION",
        "consistency": "not_established",
    }
    # LOOP-3: process loop A->B->C->A with the boundary feed entering C: the boundary-distance
    # rule tears the edge into C (s_bc), which is neither first nor last in declaration order.
    out["LOOP-3"] = {
        "connections": [
            ["s_in", "FEED", "C"],
            ["s_ab", "A", "B"],
            ["s_bc", "B", "C"],
            ["s_ca", "C", "A"],
        ],
        "boundary": ["FEED"],
        "expected_tear_stream": "s_bc",
        "consumer_boundary_distances": {"s_ab": 3, "s_bc": 1, "s_ca": 2},
    }
    return out


# --------------------------------------------------------------------------------------------
# 6. --check: executable claims about this document's own numbers
# --------------------------------------------------------------------------------------------


def check(verbose: bool = True) -> dict[str, Any]:
    rows = _rows()
    order = {rid: i for i, rid in enumerate(EQUATION_ORDER)}
    if (
        {r.row_id for r in rows} != set(EQUATION_ORDER)
        or len(rows) != 49
        or len(EQUATION_ORDER) != 49
    ):
        raise AssertionError("the transcription and the assembly order disagree")
    rows.sort(key=lambda r: order[r.row_id])
    passed: list[str] = []

    def ok(name: str, cond: bool, detail: str = "") -> None:
        if not cond:
            raise AssertionError(f"self-check failed: {name} {detail}")
        passed.append(name)
        if verbose:
            print(f"  ok  {name}{(': ' + detail) if detail else ''}")

    ok(
        "ids: 47 columns, 49 rows, all ASCII, no duplicates",
        len(VARIABLE_IDS) == 47
        and len(set(VARIABLE_IDS)) == 47
        and all(c.isascii() for c in VARIABLE_IDS)
        and all(r.isascii() for r in EQUATION_ORDER),
    )
    for r in rows:
        if r.affine is not None:
            assert set(r.affine) == set(r.columns), r.row_id
    ok("every affine row's coefficient keys are exactly its columns", True)
    variants = {
        label: analyse(rows, params, label=label) for label, params in VARIANT_PARAMETERS.items()
    }
    nominal = variants["SYN-001-nominal"]
    ok(
        "counts: 49 equations, 47 free variables, nnz 170, rank 47, unmatched 2",
        nominal["structural_counts"]
        == {"free_variables": 47, "equations": 49, "matched": 47, "unmatched": 2}
        and nominal["nnz"] == 170,
    )
    dm = nominal["dm_full"]
    row_by_id = {r.row_id: r for r in rows}
    ok(
        "DM: over-determined part is 7 pressure rows x 5 pressure columns, nothing"
        " under-determined",
        len(dm["over_rows"]) == 7
        and len(dm["over_cols"]) == 5
        and all(VARIABLE_KINDS[c] == "pressure" for c in dm["over_cols"])
        and all(row_by_id[r].kind == "pressure" for r in dm["over_rows"])
        and not dm["under_cols"],
        f"{dm['over_rows']} x {dm['over_cols']}",
    )
    ok(
        "certified rows are exactly K03 §7.2's two, in that order",
        nominal["certified_rows"] == ["U-FLASH:FLASH-P:inlet", "U-SPLIT:SPLIT-P:recycle"],
    )
    ok(
        "certificate paths equal K03 §7.2's table as signed-row sets",
        [frozenset(map(tuple, e["equals"])) for e in nominal["certificates"]["eliminated"]]
        == [
            frozenset(
                {("U-FEED:FEED-P", 1), ("U-MIX:MIX-pressure:0", -1), ("U-HEAT:HEAT-pressure", 1)}
            ),
            frozenset(
                {
                    ("U-FEED:FEED-P", 1),
                    ("U-MIX:MIX-pressure:0", -1),
                    ("U-MIX:MIX-pressure:1", 1),
                    ("U-FLASH:FLASH-P:liquid", -1),
                }
            ),
        ],
    )
    ok(
        "both mismatches exactly 0.0 at nominal; closed form P_spec - P_f",
        all(e["constant_mismatch"] == 0.0 for e in nominal["certificates"]["eliminated"])
        and all(
            e["constant_mismatch"]
            == PARAMETERS_NOMINAL["U-FEED.P_spec"] - PARAMETERS_NOMINAL["U-FLASH.P_spec"]
            for e in nominal["certificates"]["eliminated"]
        ),
    )
    ok(
        "no uncertified affine rows in SYN-001",
        nominal["certificates"]["uncertified_affine_rows"] == [],
    )
    ok(
        "nominal: STRUCTURALLY_CLOSED after certificates; excess 0, deficit 0",
        nominal["finding"] == "STRUCTURALLY_CLOSED"
        and nominal["excess"] == 0
        and nominal["deficit"] == 0,
    )
    ok(
        "excess of the full DM equals the certified rows inside it: |R+| - |C+| == |E ∩ R+|",
        len(dm["over_rows"]) - len(dm["over_cols"])
        == len(set(nominal["certified_rows"]) & set(dm["over_rows"])),
    )
    ok(
        "canonical matching's unmatched rows coincide with the certified rows (SYN-001"
        " observation, not a rule)",
        nominal["unmatched_rows_canonical"] == nominal["certified_rows"]
        and nominal["unmatched_rows_canonical"]
        == MEASURED["scipy_hopcroft_karp_unmatched_rows_nominal"],
    )
    # state independence
    for label, res in variants.items():
        same = {k: res[k] for k in res if k != "label"} == {
            k: nominal[k] for k in nominal if k != "label"
        }
        ok(f"{label}: structural results identical to nominal (state-free, parameter-free)", same)
    # 150 kPa
    conflict_p = analyse(
        rows, {**PARAMETERS_NOMINAL, "U-FLASH.P_spec": 150_000.0}, label="SYN-001-flash-150kPa"
    )
    ok(
        "flash at 150 kPa: SPECIFICATION_CONFLICT naming both certified rows, m_e ="
        " -50000.0 exactly",
        conflict_p["finding"] == "SPECIFICATION_CONFLICT"
        and conflict_p["conflicting_rows"] == nominal["certified_rows"]
        and all(
            e["constant_mismatch"] == -50_000.0 for e in conflict_p["certificates"]["eliminated"]
        ),
    )
    # conflicting heater spec
    conflicting = analyse(
        [*rows, CONFLICTING_ROW],
        {**PARAMETERS_NOMINAL, "SPEC-heater-duty.value": 50_000.0},
        label="SYN-001-conflicting-heater-spec",
    )
    ok(
        "conflicting: 50 rows, nnz 171, rank 47, unmatched 3",
        conflicting["structural_counts"]
        == {"free_variables": 47, "equations": 50, "matched": 47, "unmatched": 3}
        and conflicting["nnz"] == 171,
    )
    ok(
        "conflicting: full DM over-determined part 44 rows x 41 columns (brief §3.2)",
        len(conflicting["dm_full"]["over_rows"]) == 44
        and len(conflicting["dm_full"]["over_cols"]) == 41,
    )
    ok(
        "conflicting: certified rows unchanged; after certificates 41 rows x 40 columns, excess 1",
        conflicting["certified_rows"] == nominal["certified_rows"]
        and conflicting["excess"] == 1
        and len(conflicting["dm_after_certificates"]["over_rows"]) == 41
        and len(conflicting["dm_after_certificates"]["over_cols"]) == 40,
    )
    ok(
        "conflicting: STRUCTURAL_OVER_SPECIFICATION; 10 candidate specification rows over 9"
        " specifications",
        conflicting["finding"] == "STRUCTURAL_OVER_SPECIFICATION"
        and len(conflicting["candidate_specification_rows"]) == 10
        and len(conflicting["candidate_specifications"]) == 9,
        str(conflicting["candidate_specifications"]),
    )
    ok(
        "nominal unit DOF: feed 5/5, mixer 0/0, heater 1/1, flash 4/4, splitter 1/0; none"
        " over-specified",
        {
            u: (d["dof"], len(d["specifications"]))
            for u, d in nominal["unit_dof"].items()
            if u not in ("U-PRODUCT", "U-PURGE")
        }
        == {
            "U-FEED": (5, 5),
            "U-MIX": (0, 0),
            "U-HEAT": (1, 1),
            "U-FLASH": (4, 4),
            "U-SPLIT": (1, 0),
        }
        and nominal["over_specified_units"] == [],
    )
    ok(
        "mixer local excess: both pressure-equality rows over S2.P (ADR 0001 D4.5)",
        nominal["unit_dof"]["U-MIX"]["local_excess_rows"]
        == ["U-MIX:MIX-pressure:0", "U-MIX:MIX-pressure:1"],
    )
    ok(
        "conflicting: heater 1 dof, 2 specifications; implicated objects as the registry expects",
        conflicting["over_specified_units"] == ["U-HEAT"]
        and conflicting["implicated_objects"]
        == ["SPEC-heater-duty", "SPEC-heater-outlet-T", "U-HEAT"],
    )
    for case in (nominal, conflicting):
        tot_dof = sum(d["dof"] for d in case["unit_dof"].values())
        tot_spec = sum(len(d["specifications"]) for d in case["unit_dof"].values())
        tot_local = sum(d["model_rows"] - d["model_rank"] for d in case["unit_dof"].values())
        ok(
            f"{case['label']}: Σspecs + Σlocal_excess − Σdof == excess − deficit",
            tot_spec + tot_local - tot_dof == case["excess"] - case["deficit"],
            f"{tot_spec} + {tot_local} - {tot_dof} = {case['excess'] - case['deficit']}",
        )
    # BTF
    ok(
        "BTF of the 47x47: 24 blocks, sizes [17, 8, 1 x 22], largest fraction 17/47",
        len(nominal["btf_square"]) == 24
        and nominal["block_sizes_sorted"] == [17, 8] + [1] * 22
        and nominal["largest_block_fraction"] == 17 / 47,
    )
    big = next(b for b in nominal["btf_square"] if b["size"] == 17)
    ok(
        "the 17-block is the recycle: component flows of S2..S6 and the flash totals",
        set(big["cols"])
        == {flow(s, c) for s in ("S2", "S3", "S4", "S5", "S6") for c in COMPONENTS}
        | {"S4.N", "S5.N"},
    )
    lifted = next(b for b in nominal["btf_square"] if b["size"] == 8)
    ok(
        "the 8-block is the heater's lifted split and depends on the recycle block",
        set(lifted["cols"])
        == {
            *(f"S3.vap.{c}" for c in COMPONENTS),
            *(f"S3.liq.{c}" for c in COMPONENTS),
            "S3.V",
            "S3.L",
        }
        and nominal["btf_square"].index(big) in lifted["depends_on"],
    )
    # tear
    loop = nominal["tear"]["loops"][0]
    ok(
        "one process loop {MIX, HEAT, FLASH, SPLIT}; cycle edges S2, S3, S5, S6",
        nominal["tear"]["process_loops"] == [["U-MIX", "U-HEAT", "U-FLASH", "U-SPLIT"]]
        and loop["cycle_edges"] == ["S2", "S3", "S5", "S6"],
    )
    ok(
        "every cycle edge breaks the loop and has dimension 3; distances 2, 3, 4, 1",
        [
            (c["stream"], c["breaks_loop"], c["dimension"], c["consumer_boundary_distance"])
            for c in loop["candidates"]
        ]
        == [("S2", True, 3, 2), ("S3", True, 3, 3), ("S5", True, 3, 4), ("S6", True, 3, 1)],
    )
    ok(
        "dimension ties; boundary distance decides; S6 chosen; T and P of every candidate"
        " stay untorn",
        loop["tie_break_used"] == "boundary_distance"
        and loop["chosen_stream"] == "S6"
        and all(
            c["not_torn"] == [temp(c["stream"]), pres(c["stream"])] for c in loop["candidates"]
        ),
    )
    ok(
        "tear variables S6.n.{A,B,C}; tear rows SPLIT-recycle:{A,B,C}; inner 44x44 closed",
        loop["tear_variables"] == ["S6.n.A", "S6.n.B", "S6.n.C"]
        and loop["tear_rows"]
        == ["U-SPLIT:SPLIT-recycle:A", "U-SPLIT:SPLIT-recycle:B", "U-SPLIT:SPLIT-recycle:C"]
        and (loop["inner_rows"], loop["inner_cols"]) == (44, 44)
        and loop["inner_closed"],
    )
    ok(
        "inner BTF: 30 blocks, sizes [8, 8, 1 x 28]",
        sorted(loop["inner_block_sizes"], reverse=True) == [8, 8] + [1] * 28,
    )
    ok(
        "signature rule: the flash block is upstream of the tear rows, the heater's lifted"
        " block is not",
        loop["signature"]["signature_units"] == ["U-FLASH"]
        and [p["upstream_of_tear"] for p in loop["signature"]["phase_selecting"]] == [False, True],
    )
    # order independence
    inc = incidence_of(rows)
    rng = random.Random(20260923)
    certified_varies = False
    for _ in range(20):
        prow = list(inc.rows)
        rng.shuffle(prow)
        pcol = list(inc.cols)
        rng.shuffle(pcol)
        pinc = Incidence(tuple(prow), tuple(pcol), {r: inc.adj[r] for r in prow})
        pdm = dulmage_mendelsohn(pinc, maximum_matching(pinc))
        assert set(pdm["over_rows"]) == set(dm["over_rows"]) and set(pdm["over_cols"]) == set(
            dm["over_cols"]
        )
        prows = sorted(rows, key=lambda r: prow.index(r.row_id))
        pres_ = analyse(prows, PARAMETERS_NOMINAL, label="perm")
        # The *identity* of the certified rows is order-canonical (K03 §7.2 "assembled order"):
        # another row order certifies another row of the same cycle. Their number and the
        # closure verdict are invariant, and so is the column set the cycles span.
        assert len(pres_["certified_rows"]) == 2 and pres_["finding"] == "STRUCTURALLY_CLOSED"
        assert set(pres_["dm_full"]["over_cols"]) == set(dm["over_cols"])
        if set(pres_["certified_rows"]) != set(nominal["certified_rows"]):
            certified_varies = True
        assert pres_["block_sizes_sorted"] == nominal["block_sizes_sorted"]
        assert pres_["tear"]["loops"][0]["tear_variables"] == loop["tear_variables"]
        assert pres_["tear"]["loops"][0]["signature"]["signature_units"] == ["U-FLASH"]
    ok(
        "under 20 seeded row/column permutations: same DM sets, certified count and"
        " closure, block sizes, tear set, signature",
        True,
    )
    ok(
        "under those permutations the identity of the certified rows changes"
        " (order-canonical, not invariant)",
        certified_varies,
    )
    syn = synthetic_fixtures()
    ok(
        "SQ-1: rank 2, over {r1,r2}x{x1}, under {r3}x{x2,x3}, unmatched 2",
        syn["SQ-1"]["structural_rank"] == 2
        and syn["SQ-1"]["dm"]["over_rows"] == ["r1", "r2"]
        and syn["SQ-1"]["dm"]["under_cols"] == ["x2", "x3"]
        and syn["SQ-1"]["structural_counts"]["unmatched"] == 2,
    )
    ok(
        "SQ-2 closed; UND-1 deficit 1; OVR-1 excess 1 over a 2x1 block",
        syn["SQ-2"]["structural_rank"] == 2
        and not syn["SQ-2"]["dm"]["over_rows"]
        and syn["UND-1"]["dm"]["under_cols"] == ["x1", "x2", "x3"]
        and syn["OVR-1"]["dm"]["over_rows"] == ["r1", "r2"]
        and syn["OVR-1"]["dm"]["over_cols"] == ["x1"],
    )
    ok(
        "TIE-1: canonical matching x1->r2, x2->r1",
        syn["TIE-1"]["canonical_matching"] == {"x1": "r2", "x2": "r1"},
    )
    ok("BTF-1: block order a, b, c, d", syn["BTF-1"]["block_order"] == [["a"], ["b"], ["c"], ["d"]])
    ok(
        "UNC-1: three-column row is uncertified and retained; nothing certified",
        syn["UNC-1"]["uncertified_affine_rows"] == ["p4"] and syn["UNC-1"]["certified"] == [],
    )
    return {
        "variants": variants,
        "conflicting": conflicting,
        "flash_150kPa": conflict_p,
        "synthetic": syn,
        "checks_passed": passed,
    }


# --------------------------------------------------------------------------------------------
# 7. --emit
# --------------------------------------------------------------------------------------------


def _plain(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    return value


def document(result: dict[str, Any]) -> dict[str, Any]:
    rows = sorted(_rows(), key=lambda r: EQUATION_ORDER.index(r.row_id))
    nominal = result["variants"]["SYN-001-nominal"]
    conflicting = result["conflicting"]
    loop = nominal["tear"]["loops"][0]

    def case_block(res: dict[str, Any]) -> dict[str, Any]:
        return {
            "structural_counts": res["structural_counts"],
            "nnz": res["nnz"],
            "finding": res["finding"],
            "dm_full": res["dm_full"],
            "certified_rows": res["certified_rows"],
            "certificates": [
                {
                    k: e[k]
                    for k in ("row_id", "equals", "constant_mismatch", "tolerance", "consistent")
                }
                for e in res["certificates"]["eliminated"]
            ],
            "uncertified_affine_rows": res["certificates"]["uncertified_affine_rows"],
            "dm_after_certificates": res["dm_after_certificates"],
            "excess": res["excess"],
            "deficit": res["deficit"],
            "candidate_specification_rows": res["candidate_specification_rows"],
            "candidate_specifications": res["candidate_specifications"],
            "unit_degrees_of_freedom": {
                u: {
                    k: d[k]
                    for k in (
                        "columns",
                        "model_rows",
                        "model_rank",
                        "dof",
                        "specifications",
                        "specification_rows",
                        "over_specified",
                        "local_excess_rows",
                    )
                }
                for u, d in res["unit_dof"].items()
            },
            "over_specified_units": res["over_specified_units"],
            "implicated_objects": res["implicated_objects"],
            "canonical_matching": res["canonical_matching"],
            "unmatched_rows_canonical": res["unmatched_rows_canonical"],
        }

    return _plain(
        {
            "generated_by": "Fable 5.1, docs/derivations/scripts/t01_reference.py, from the"
            " SYN-001 equations "
            "(derivation §4, lifted form of ADR 0001 D2.5) transcribed by hand, the plan §3.2 "
            "topology, and the definitions of T01-structural-spec.md; every algorithm written "
            "from its definition",
            "specification": "docs/derivations/T01-structural-spec.md",
            "independence": "closed-form structural expectations; no compiler, graph-layer,"
            " solver, oracle or "
            "process_runtime code was used. The `measured` block is observation from a probe "
            "of main@f603e9b, labelled as such and never an expectation.",
            "declaration": {
                "variable_ids": list(VARIABLE_IDS),
                "variable_kinds": VARIABLE_KINDS,
                "equation_ids": list(EQUATION_ORDER),
                "row_kinds": {r.row_id: r.kind for r in rows},
                "row_unit": {r.row_id: r.unit for r in rows},
                "row_specification": {r.row_id: r.specification for r in rows if r.specification},
                "incidence": {r.row_id: list(r.columns) for r in rows},
                "affine_rows": {
                    r.row_id: {
                        "coefficients": dict(r.affine),
                        "constant": [[s, p] for s, p in r.constant],
                    }
                    for r in rows
                    if r.affine is not None
                },
                "parameters_nominal": PARAMETERS_NOMINAL,
                "variant_parameters": VARIANT_PARAMETERS,
                "connections": [list(c) for c in CONNECTIONS],
                "boundary_units": list(BOUNDARY_UNITS),
                "phase_selecting_units": list(PHASE_SELECTING_UNITS),
                "conflicting_row": {
                    "row_id": CONFLICTING_ROW.row_id,
                    "unit": CONFLICTING_ROW.unit,
                    "kind": CONFLICTING_ROW.kind,
                    "columns": list(CONFLICTING_ROW.columns),
                    "specification": CONFLICTING_ROW.specification,
                    "parameter": "SPEC-heater-duty.value",
                    "value": 50000.0,
                },
            },
            "kind_tolerances": KIND_TOLERANCE,
            "cases": {
                "SYN-001-nominal": case_block(nominal),
                "SYN-001-conflicting-heater-spec": case_block(conflicting),
                "SYN-001-flash-150kPa": case_block(result["flash_150kPa"]),
            },
            "state_free": {"identical_across": list(VARIANT_PARAMETERS)},
            "block_triangular_form": {
                "square_system": "the 47 rows after the two certified rows are removed,"
                " over the 47 columns",
                "blocks": [
                    {
                        "rows": b["rows"],
                        "cols": b["cols"],
                        "size": b["size"],
                        "depends_on": b["depends_on"],
                    }
                    for b in nominal["btf_square"]
                ],
                "block_sizes_sorted": nominal["block_sizes_sorted"],
                "block_count": len(nominal["btf_square"]),
                "largest_block_fraction": {
                    "rational": "17/47",
                    "double": nominal["largest_block_fraction"],
                },
            },
            "tear": {
                "process_loops": nominal["tear"]["process_loops"],
                "loop": {
                    k: loop[k]
                    for k in (
                        "units",
                        "cycle_edges",
                        "candidates",
                        "chosen_stream",
                        "tie_break_used",
                        "tear_variables",
                        "tear_rows",
                        "inner_rows",
                        "inner_cols",
                        "inner_closed",
                    )
                },
                "inner_blocks": [
                    {
                        "rows": b["rows"],
                        "cols": b["cols"],
                        "size": b["size"],
                        "depends_on": b["depends_on"],
                    }
                    for b in loop["inner_blocks"]
                ],
                "inner_block_sizes_sorted": sorted(loop["inner_block_sizes"], reverse=True),
                "signature": loop["signature"],
            },
            "synthetic": result["synthetic"],
            "measured": MEASURED,
            "checks_passed": result["checks_passed"],
        }
    )


def emit(path: Path, result: dict[str, Any]) -> str:
    text = yaml.safe_dump(document(result), sort_keys=False, allow_unicode=True, width=100)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="re-derive every identity and print the checks"
    )
    parser.add_argument("--emit", metavar="PATH", help="write the reference YAML")
    args = parser.parse_args(argv)
    if not args.check and not args.emit:
        parser.error("choose --check and/or --emit PATH")
    result = check(verbose=args.check)
    if args.emit:
        digest = emit(Path(args.emit), result)
        print(f"wrote {args.emit}\nsha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
