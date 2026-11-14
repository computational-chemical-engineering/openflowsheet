"""The lifted-split vocabulary: regimes, closure types, branches and per-split forms (T03, T05b).

A unit declares its lifted splits and their forms with these types, and the region solver
(`orchestrator.region`) consumes them; `region` re-exports every name. The solver's row
tolerances are not here but in `models.lifted_tolerance`, so that the verifier, which reads
`LiftedSplit`, does not reach them (R-016).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Literal

from openflowsheet.compiled import PhaseSignature

#: An attempt's regime of one lifted split. `ZERO_FLOW` (T05b spec §7; ADR 0012 D4 (c)) is selected
#: only under `T05b-phase-contract-v2`, exactly when the split's feed is dormant.
Regime = Literal["TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW"]
#: T05b spec §6.1 (ADR 0012 D3): whether a lifted split's unit fixes its temperature by an energy
#: row (`PH`: the valve, the PH flash, the duty-mode reactor) or by a specification (`TP`).
ClosureType = Literal["PH", "TP"]
#: A split's branch found at a state (`roots.branch_found`): a regime, or `ZERO_FLOW` when it
#: carries nothing in either phase (ADR 0012 D6). Not an attempt regime under v1.
Branch = Literal["TWO_PHASE", "LIQUID", "VAPOR", "ZERO_FLOW"]

#: T03 §4.10's `inadmissible(<stream>, <branch>)` vocabulary, with T05b spec §6.5's `zero_flow`
#: (a `ZERO_FLOW` branch whose feed flows at closure). A `TWO_PHASE` branch is always admissible.
INADMISSIBLE_BRANCH: Final[Mapping[str, str]] = {
    "LIQUID": "all_liquid",
    "VAPOR": "all_vapor",
    "ZERO_FLOW": "zero_flow",
}


@dataclass(frozen=True)
class LiftedSplit:
    """One lifted phase split: the variables that carry it and the rows that define it."""

    unit: str
    #: The stream being split, for messages and for the admissibility check's subject.
    stream: str
    feed: tuple[str, ...]
    temperature: str
    pressure: str
    vapor: tuple[str, ...]
    liquid: tuple[str, ...]
    vapor_total: str
    liquid_total: str
    equilibrium_rows: tuple[str, ...]
    vapor_definition: str
    liquid_definition: str

    def pinned(self, regime: Regime) -> tuple[str, ...]:
        """§6.3.1: LIQUID pins the vapour side, VAPOR the liquid side, TWO_PHASE nothing.
        `ZERO_FLOW`'s pins are its `ZeroFlowForm`'s (T05b spec §7.2), never read here."""
        if regime == "ZERO_FLOW":
            raise ValueError(f"defect: {self.unit}'s ZERO_FLOW pins are its ZeroFlowForm's")
        if regime == "LIQUID":
            return (*self.vapor, self.vapor_total)
        if regime == "VAPOR":
            return (*self.liquid, self.liquid_total)
        return ()

    def dropped(self, regime: Regime) -> tuple[str, ...]:
        """The rows a pinned phase satisfies identically; dropping them keeps the system square.
        `ZERO_FLOW`'s are its `ZeroFlowForm`'s (T05b spec §7.2), never read here."""
        if regime == "ZERO_FLOW":
            raise ValueError(f"defect: {self.unit}'s ZERO_FLOW rows are its ZeroFlowForm's")
        if regime == "LIQUID":
            return (*self.equilibrium_rows, self.vapor_definition)
        if regime == "VAPOR":
            return (*self.equilibrium_rows, self.liquid_definition)
        return ()


@dataclass(frozen=True)
class ZeroFlowForm:
    """One lifted split's `ZERO_FLOW` form (T05b spec §7.2; ADR 0012 D4 (c)): what an attempt
    in that regime pins and drops, and — for a PH-type split — the label row it adds in place of
    its unit's energy row. Built from the split registry's ids (spec §6.1,
    `splits.zero_flow_forms`), beside the split's descriptor rather than inside it, so
    `LiftedSplit` (and its registered `repr` digest, T05 W1.a) does not move.

    The label row is a row of the attempt's system only — never of the compiled declaration — so
    no `model_version`, structure hash or T01 report moves (spec §7.2)."""

    unit: str
    #: The split's lifted flows and totals, pinned at `+0.0`.
    columns: tuple[str, ...]
    #: The rows the form drops: equilibrium, split (or the products' mole) rows, the two total
    #: definitions, and for a PH-type split its energy row, last.
    rows: tuple[str, ...]
    #: A PH-type split's energy row, swapped out for the label (`""` for a TP-type split).
    swapped: str = ""
    #: `(row id, T_out, T_label)` of a PH-type split's label row `T_out − T_label`; `None` for a
    #: TP-type split, whose temperature keeps its specification row.
    label: tuple[str, str, str] | None = None


@dataclass(frozen=True)
class VapourOnlyForm:
    """One lifted split's vapour-only liquid flows (M02 design note §14.2 B12–B13; ADR 0012
    Amendment A2): the components whose liquid flow is a structural zero (the C1 flash's light
    gases), fixed by zero rows `l_i = 0` in the equilibrium family. A `TWO_PHASE` attempt pins
    `columns` at `+0.0` and drops `rows`; VAPOR and ZERO_FLOW pin them already, and LIQUID leaves
    them to the mole rows. Built by `splits.vapour_only_forms`, beside the descriptor as
    `ZeroFlowForm` is, so `LiftedSplit` and its registered `repr` digest do not move."""

    unit: str
    #: The split's liquid flows of the vapour-only components, in component order.
    columns: tuple[str, ...]
    #: Their zero rows, in the same order.
    rows: tuple[str, ...]


@dataclass(frozen=True)
class DormancyForm:
    """The zero-flow form of one dormancy-form outlet of a unit without a lifted split (T05b spec
    §7.6–§7.7; ADR 0012 D12): at exact dormancy of every stream of its trigger port it swaps one
    row — the unit's energy row, whose `T_out` coefficient `−Σ n c_p` is then zero — for the label
    row `T_out − T_label`, and pins nothing. Built from the dormancy-form registry
    (`splits.dormancy_forms`) and checked by `splits.check_agreement` (g).

    An attempt that runs the form carries the signature item `(item, "ZERO_FLOW")` after its
    lifted regimes (spec §7.8 (i)); the label row is a row of the attempt's system only, never of
    the compiled declaration."""

    #: `<U>.<port>`: the signature item's key.
    item: str
    unit: str
    #: The ports the rule names: the outlet, and the port whose every stream is the trigger.
    outlet_port: str
    trigger_port: str
    #: The outlet stream, and the trigger port's streams in connection order (R1).
    outlet: str
    triggers: tuple[str, ...]
    #: Every flow column of every trigger stream: the form is selected when all are `+0.0`.
    trigger_flows: tuple[str, ...]
    #: Spec §7.8 (ii)'s outlet reset: per component, the outlet's flow column and the trigger
    #: streams' flow columns it is the sum of, in connection order.
    balance: tuple[tuple[str, tuple[str, ...]], ...]
    #: The row swapped out, and the label row `(row id, T_out, T_label)` swapped in.
    swapped: str
    label: tuple[str, str, str]
    #: The outlet's declared phase, which names the item's absence in a cause string (§7.8 (i)).
    declared: PhaseSignature


@dataclass(frozen=True)
class StagedSplits:
    """The lifted splits of one *staged unit* (S11 design note §10.2, R-822): an instance whose
    rows describe several splits (its model is in `splits.STAGED_MODELS`; the column's
    equilibrium stages). Each split's `unit` is its **key**, an opaque string the instance owns;
    the instance is the split's **owner**. The per-split maps sit beside the descriptors, as the
    registry's do, keyed by the split key; there are no vapour-only forms (a staged unit that
    needs them is a design-lane amendment).

    `other_squared_rows` are the instance's `molar_flow_squared` rows that are no split's
    equilibrium rows (§10.3): its own statement, so `splits.check_agreement` still leaves no such
    row unclaimed."""

    splits: tuple[LiftedSplit, ...]
    closure_types: Mapping[str, ClosureType]
    zero_flow_forms: Mapping[str, ZeroFlowForm]
    split_temperatures: Mapping[str, tuple[str, ...]]
    other_squared_rows: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        keys = [split.unit for split in self.splits]
        if not keys:
            raise ValueError("staged_splits_empty: a staged unit supplies at least one split")
        if len(set(keys)) != len(keys):
            raise ValueError(f"staged_split_keys_repeated: {keys}")
        for name in ("closure_types", "zero_flow_forms", "split_temperatures"):
            found = set(getattr(self, name))
            if found != set(keys):
                raise ValueError(
                    f"staged_split_map_disagrees({name}): keys {sorted(found)}, splits "
                    f"{sorted(keys)}"
                )


#: T05b spec §7.2: a label row's kind, and so its tolerance and its row scale (K03 §4.2's
#: temperature nominal); a PTC core reads it as algebraic (spec §7.8 (v), ADR 0008 D3).
LABEL_KIND: Final = "temperature"
