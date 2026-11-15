"""The region's Newton problem over lifted splits (T03 §4, T05b §7): one attempt's system.

`_region_problem` builds an attempt's square system (its rows over its free columns, K03's
Newton problem) with the label rows `T_out − T_label` of the swapped energy rows (`_labels`,
`_label_matrix`, T05b §7.2); the opening fixed point (`_opening_order`, `_settle`,
`_rederive`) with its dormancy-outlet resets (`_reset_outlet`, T05b §7.8 (ii)); and
`_LiftedOps`, the lifted EO path's side of the phase contract for one attempt (T03 §4.3, §4.6,
§4.7).

Split from `orchestrator.region` (S19 B1), which re-exports what its callers and tests read here.
Of the region solver this module imports only `region_phase`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
import numpy.typing as npt
import scipy.sparse as sp

from openflowsheet.compile.spec import ProblemSpec
from openflowsheet.compiled import CompiledProblem, EvaluationContext
from openflowsheet.models.lifted import (
    INADMISSIBLE_BRANCH,
    LABEL_KIND,
    Branch,
    DormancyForm,
    LiftedSplit,
    Regime,
    VapourOnlyForm,
    ZeroFlowForm,
)
from openflowsheet.models.lifted_tolerance import KIND_TOLERANCE
from openflowsheet.numerics.newton import (
    Evaluation,
    JacobianUnavailableError,
    NewtonResult,
    Problem,
)
from openflowsheet.numerics.scaling import REGISTERED_NOMINALS, Scaling
from openflowsheet.orchestrator.execution import Region
from openflowsheet.orchestrator.phase_contract import (
    Candidate,
    Conversion,
    OpeningNotSettledError,
    OpeningRefusal,
    OpeningRequirement,
    OpeningState,
    check_opening,
)
from openflowsheet.orchestrator.region_phase import (
    ClosureMemo,
    _admissible,
    _branch,
    _contract_kernel,
    _dormant_feed,
    _form,
    _KernelAnswer,
    _pin,
    _pinned,
    _zero_flow_answer,
)
from openflowsheet.orchestrator.roots import branch_found
from openflowsheet.orchestrator.trace import AttemptSignature, SolvePolicy
from openflowsheet.thermo import PropertyProvider


def _labels(
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    forms: Mapping[str, ZeroFlowForm],
) -> tuple[tuple[str, str, str], ...]:
    """The label rows `(row id, T_out, T_label)` of the attempt's PH-type `ZERO_FLOW` splits, in
    signature order (T05b spec §7.2)."""
    labels: list[tuple[str, str, str]] = []
    for split in splits:
        if regimes[split.unit] == "ZERO_FLOW":
            label = _form(split, forms).label
            if label is not None:
                labels.append(label)
    return tuple(labels)


def _region_problem(
    compiled: CompiledProblem,
    context: EvaluationContext,
    spec: ProblemSpec,
    scaling: Scaling,
    base: Mapping[str, float],
    free: Sequence[str],
    rows: Sequence[str],
    screen: Callable[[dict[str, float]], AttemptSignature | Evaluation] | None = None,
    opening: npt.NDArray[np.float64] | None = None,
    labels: Sequence[tuple[str, str, str]] = (),
) -> Problem:
    """One attempt's square system: its rows over its free columns, everything else held at `base`.

    The residual and the Jacobian are the compiled problem's, selected **by id**, never by
    position (§6.1), so the region solves exactly the function K04 verifies.

    `labels` (T05b spec §7.2) are the attempt's label rows `(row id, T_out, T_label)`, appended
    after `rows`: residual `T_out − T_label`, derivative exactly `+1` at `T_out` and `−1` at
    `T_label` where those are free columns, kind temperature. They are not compiled rows. With
    none, the problem is the one it always was.

    `screen` (T03 §4.3) reports each trial's signature: the frozen one, or the kernel's regime for a
    single-phase unit whose admissibility check flagged the trial — or, when the kernel refuses,
    the typed evaluation to return instead. It reads a trial; it never changes the residual. The
    `opening` point is not screened (an attempt may open where its own screen would object).
    """
    order = {name: index for index, name in enumerate(spec.variable_ids)}
    rows_at = {name: index for index, name in enumerate(spec.equation_ids)}
    selected_rows = [rows_at[name] for name in rows]
    selected_columns = [order[name] for name in free]
    held = np.array([base[name] for name in spec.variable_ids], dtype=np.float64)
    label_ids = tuple(label for label, _, _ in labels)
    label_columns = [(order[outlet], order[source]) for _, outlet, source in labels]
    label_matrix = _label_matrix(labels, free)

    def full(x: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        vector = held.copy()
        vector[selected_columns] = x
        return vector

    def residual(x: npt.NDArray[np.float64]) -> Evaluation:
        vector = full(x)
        result = compiled.residual(vector, context)
        if result.status != "ok" or result.values is None:
            return Evaluation(status=result.status, message=result.message)
        values = tuple(result.values[i] for i in selected_rows)
        if labels:
            values += tuple(float(vector[o]) - float(vector[s]) for o, s in label_columns)
        if screen is None or (opening is not None and np.array_equal(x, opening)):
            return Evaluation(status="ok", values=values)
        reported = screen(dict(zip(spec.variable_ids, (float(v) for v in vector), strict=True)))
        if isinstance(reported, Evaluation):
            return reported
        return Evaluation(status="ok", values=values, signature=reported)

    def jacobian(x: npt.NDArray[np.float64]) -> sp.csc_matrix:
        result = compiled.jacobian(full(x), context)
        if result.status != "ok":
            # T04 review M1: a failed evaluation carries empty data; read as a matrix it would be
            # a structurally valid zero, which a core then factors.
            raise JacobianUnavailableError(str(result.status), result.message)
        matrix = sp.csc_matrix(
            (result.data, result.indices, result.indptr),
            shape=(len(result.row_ids), len(result.col_ids)),
        )
        selected = matrix[selected_rows, :][:, selected_columns]
        if labels:
            return sp.csc_matrix(sp.vstack([selected, label_matrix]))
        return sp.csc_matrix(selected)

    return Problem(
        variable_ids=tuple(free),
        row_ids=(*rows, *label_ids),
        residual=residual,
        jacobian=jacobian,
        scaling=Scaling(
            column={name: scaling.column[name] for name in free},
            row={
                **{name: scaling.row[name] for name in rows},
                **dict.fromkeys(label_ids, REGISTERED_NOMINALS[LABEL_KIND]),
            },
        ),
        row_tolerance={
            **{name: KIND_TOLERANCE[spec.row_kinds[name]] for name in rows},
            **dict.fromkeys(label_ids, KIND_TOLERANCE[LABEL_KIND]),
        },
        lower_bounds={name: 0.0 for name in free if spec.variable_kinds.get(name) == "molar_flow"},
    )


def _refinement(
    policy: SolvePolicy, spec: ProblemSpec, free: Sequence[str]
) -> dict[str, float] | None:
    """ADR 0018 D1–D2: under `eo_core = "newton_refined"`, the terminal refinement's `τ_kind` for
    every free column whose declared quantity kind has a registered acceptance rule — the rule
    the rows are judged by (`KIND_TOLERANCE`); `None`, which is K03's Newton unchanged, under any
    other value. Label rows are rows, not columns, so they add nothing here."""
    if policy.globalization.eo_core != "newton_refined":
        return None
    return {
        name: KIND_TOLERANCE[kind]
        for name in free
        if (kind := spec.variable_kinds.get(name)) is not None and kind in KIND_TOLERANCE
    }


def _with_labels(labels: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    """`_region_problem`'s `labels` argument, passed only when there are any: an attempt without
    a label row calls it exactly as before T05b W7."""
    return {"labels": tuple(labels)} if labels else {}


def _label_matrix(labels: Sequence[tuple[str, str, str]], free: Sequence[str]) -> sp.csc_matrix:
    """The label rows' exact Jacobian over the free columns: `+1` at `T_out`, `−1` at `T_label`
    (T05b spec §7.2); a held column has no entry."""
    at = {name: index for index, name in enumerate(free)}
    data: list[float] = []
    row_index: list[int] = []
    column_index: list[int] = []
    for k, (_, outlet, source) in enumerate(labels):
        for name, value in ((outlet, 1.0), (source, -1.0)):
            if name in at:
                data.append(value)
                row_index.append(k)
                column_index.append(at[name])
    return sp.csc_matrix(
        sp.coo_matrix(
            (np.asarray(data, dtype=np.float64), (row_index, column_index)),
            shape=(len(labels), len(free)),
        )
    )


def _label_entries(labels: Sequence[tuple[str, str, str]]) -> tuple[tuple[str, str], ...]:
    """The label rows' structural entries, for the attempt's `jacobian_pattern` (spec §7.2)."""
    return tuple((label, name) for label, outlet, source in labels for name in (outlet, source))


def _trigger_dormant(form: DormancyForm, state: Mapping[str, float]) -> bool:
    """ADR 0001 D3.1: every flow of every trigger stream exactly zero (`-0.0 == 0.0`)."""
    return all(state[name] == 0.0 for name in form.trigger_flows)


def _items(forms: Sequence[DormancyForm], state: Mapping[str, float]) -> AttemptSignature:
    """T05b spec §7.8 (i)–(ii): the item `(<U>.<port>, ZERO_FLOW)` of every form whose trigger
    streams are exactly dormant at `state`, in declaration order (the exchanger's hot side first).
    """
    return tuple((form.item, "ZERO_FLOW") for form in forms if _trigger_dormant(form, state))


#: One entry of an opening's fixed point: a lifted split or a dormancy-form outlet.
type OpeningEntry = LiftedSplit | DormancyForm


def _opening_order(
    splits: Sequence[LiftedSplit],
    dormancy: Sequence[DormancyForm],
    units: Sequence[str],
    owners: Mapping[str, str] | None = None,
) -> tuple[OpeningEntry, ...]:
    """T05b spec §7.8 (ii) 1's pass order: units in declaration order (`units`, the region's);
    within a unit its lifted split, then its dormancy-form outlets as `dormancy` lists them (an
    exchanger's hot before cold). A staged unit's splits (S11 §10.2) sit at their owner's
    position, in the order supplied."""
    at = {unit: index for index, unit in enumerate(units)}
    owner = owners or {}
    keyed: list[tuple[tuple[int, int, int], OpeningEntry]] = [
        ((at[owner.get(split.unit, split.unit)], 0, k), split) for k, split in enumerate(splits)
    ]
    keyed += [((at[form.unit], 1, k), form) for k, form in enumerate(dormancy)]
    return tuple(entry for _, entry in sorted(keyed, key=lambda pair: pair[0]))


def _same(a: float, b: float) -> bool:
    """Bitwise equality of two finite doubles as ADR 0001 D3.1 reads them: `+0.0` is not `-0.0`."""
    return a == b and math.copysign(1.0, a) == math.copysign(1.0, b)


def _reset_outlet(state: dict[str, float], form: DormancyForm) -> bool:
    """T05b spec §7.8 (ii)'s outlet reset: the outlet's flows set to its mole balance at `state` —
    pump and exchanger side `n_out,i := n_in,i`, mixer `n_out,i := Σ_k n_in(k),i` summed in
    connection order — wherever they differ from it; exactly `+0.0` on entering (a dormant sum is
    `+0.0`, never `-0.0`). Its temperature keeps its value (the label row closes it on entering,
    the energy row on leaving). On leaving, without it the declared energy row's `T_out`
    coefficient `−Σ n_out c_p` is still zero and the first Jacobian singular (F7). Whether it
    wrote anything."""
    written = False
    for outlet, inlets in form.balance:
        value = state[inlets[0]]
        for name in inlets[1:]:
            value += state[name]
        value += 0.0
        if not _same(state[outlet], value):
            state[outlet] = value
            written = True
    return written


@dataclass(frozen=True)
class _SplitChange:
    """One lifted split's regime change in an opening's fixed point: the split, its branch before
    the change (for attempt 0's `projected(<S>, <branch>, <regime>)` record) and its new regime."""

    split: LiftedSplit
    branch: str
    regime: Regime


def _settle(
    state: Mapping[str, float],
    regimes: Mapping[str, Regime],
    *,
    order: Sequence[OpeningEntry],
    reference: frozenset[str],
    leave: Callable[[LiftedSplit, Mapping[str, float]], _KernelAnswer],
) -> tuple[dict[str, float], dict[str, Regime], dict[str, str], list[_SplitChange]]:
    """T05b spec §7.8 (ii) as amended (Q-S9, R-065; review M1, N1): an opening made consistent
    with exact dormancy, under v2.

    Passes over `order` (`_opening_order`) until one changes nothing. Each pass, per entry:
    **(a)** a lifted split whose feed is exactly dormant and whose regime is not `ZERO_FLOW`
    enters it (§7.4: its lifted flows set to `+0.0`, every other value kept); a split in
    `ZERO_FLOW` whose feed flows leaves it (§7.4: regime and split from `leave`, the provider's TP
    flash at the current state); **(b)** a dormancy-form outlet whose item — read off the current
    state — differs from its `reference` (the previous attempt's items, or at attempt 0 the
    supplied start's) has its flows reset to its mole balance wherever they differ from it, so a
    reset made stale by a later write is redone.

    With `m = len(order)`, an acyclic propagation settles within `m` passes whatever the
    declaration order; a pass `m + 1` that still changes something raises
    `OpeningNotSettledError` naming the first entry (unit id or item key) it changed.

    Returns the settled state and regimes, F2's record (`unit → kernel`, spec §6.5) of each split
    that left `ZERO_FLOW` and did not re-enter it, and every split change in order."""
    opened, settled = dict(state), dict(regimes)
    records: dict[str, str] = {}
    changes: list[_SplitChange] = []
    for index in range(len(order) + 1):
        changed = [
            identifier
            for entry in order
            if (identifier := _rederive(entry, opened, settled, reference, leave, records, changes))
        ]
        if not changed:
            return opened, settled, records, changes
        if index == len(order):
            raise OpeningNotSettledError(changed[0])
    raise AssertionError("unreachable: the last pass returns or raises")


def _rederive(
    entry: OpeningEntry,
    state: dict[str, float],
    regimes: dict[str, Regime],
    reference: frozenset[str],
    leave: Callable[[LiftedSplit, Mapping[str, float]], _KernelAnswer],
    records: dict[str, str],
    changes: list[_SplitChange],
) -> str:
    """One entry of one pass of `_settle`, in place: the entry's id (unit id or item key) if it
    changed the opening, else `""`."""
    if isinstance(entry, DormancyForm):
        if _trigger_dormant(entry, state) == (entry.item in reference):
            return ""
        return entry.item if _reset_outlet(state, entry) else ""
    split = entry
    dormant = _dormant_feed(split, state)
    if dormant == (regimes[split.unit] == "ZERO_FLOW"):
        return ""
    branch = _branch(split, state, v2=True)
    answer = _zero_flow_answer(split) if dormant else leave(split, state)
    state.update(answer.values)
    regimes[split.unit] = answer.regime
    records.pop(split.unit, None)
    if answer.fallback:
        records[split.unit] = answer.fallback
    changes.append(_SplitChange(split, branch, answer.regime))
    return split.unit


def _watched_variables(
    splits: Sequence[LiftedSplit],
    regimes: Mapping[str, Regime],
    state: Mapping[str, float],
) -> dict[str, tuple[str, str, str]]:
    """T03 §4.6: the lifted variables whose persistent block means a phase leaves.

    Only a `TWO_PHASE` unit's: each phase's total while the stream flows, and each phase component
    while the stream's own component is positive (T02 §6.3.3's premise, unchanged: with finite,
    positive K-values a flowing phase cannot hold a zero component at a two-phase root). A
    single-phase unit watches nothing: its one phase cannot leave while the stream flows, and a
    component vanishing there is the stream's own (ADR 0001 D3.3), not a phase event.
    """
    watched: dict[str, tuple[str, str, str]] = {}
    for split in splits:
        if regimes[split.unit] != "TWO_PHASE":
            continue
        if sum(state[name] for name in split.feed) <= 0.0:
            continue
        for phase, total, components in (
            ("vapor", split.vapor_total, split.vapor),
            ("liquid", split.liquid_total, split.liquid),
        ):
            watched[total] = (split.unit, phase, total)
            for component, feed in zip(components, split.feed, strict=True):
                if state[feed] > 0.0:
                    watched[component] = (split.unit, phase, component)
    return watched


def _branch_found(split: LiftedSplit, state: Mapping[str, float]) -> Branch:
    """K03 §8.2's branch found for one split (`roots.branch_found`, the one definition)."""
    ((_, branch),) = branch_found([split], state)
    return branch  # type: ignore[return-value]


def _units_and_items_disjoint(
    splits: Sequence[LiftedSplit], dormancy: Sequence[DormancyForm]
) -> None:
    """S08b §5.1 (R-790): a signature entry is an item iff its key is a dormancy item, so no
    lifted unit id may also be an item key. No registered region reaches the raise."""
    clash = {split.unit for split in splits} & {form.item for form in dormancy}
    if clash:
        raise ValueError(f"defect: {sorted(clash)} are both lifted units and dormancy items")


class _LiftedOps:
    """The lifted EO path's side of the contract (T03 §4.3, §4.6, §4.7), for one attempt.

    An opening here is `(state, regimes)`: a full state over the declaration's variables with
    every lifted split set for the regimes it opens under.
    """

    lifted = True

    def __init__(
        self,
        *,
        splits: Sequence[LiftedSplit],
        regimes: Mapping[str, Regime],
        end_state: Mapping[str, float],
        free: Sequence[str],
        provider: PropertyProvider,
        context: EvaluationContext,
        policy: SolvePolicy,
        region: Region,
        spec: ProblemSpec,
        identity: tuple[str, str],
        ph_units: frozenset[str] = frozenset(),
        v2: bool = False,
        forms: Mapping[str, ZeroFlowForm] | None = None,
        dormancy: Sequence[DormancyForm] = (),
        items: frozenset[str] = frozenset(),
        order: Sequence[OpeningEntry] = (),
        temperatures: Mapping[str, tuple[str, ...]] | None = None,
        memo: ClosureMemo | None = None,
        vapour_only: Mapping[str, VapourOnlyForm] | None = None,
    ) -> None:
        self._splits = splits
        self._regimes = dict(regimes)
        self._end = dict(end_state)
        self._free = tuple(free)
        self._provider = provider
        self._context = context
        self._policy = policy
        self._region = region
        self._spec = spec
        self._identity = identity
        #: The PH-type units under v2 (T05b spec §6.2); empty under v1.
        self._ph_units = ph_units
        #: T05b spec §7: whether `ZERO_FLOW` is a regime (v2), and each split's form.
        self._v2 = v2
        self._forms = forms or {}
        #: M02 design note §14.2 B13: each split's vapour-only form (empty for SYN-001).
        self._vapour_only = vapour_only or {}
        #: T05b spec §7.8: the region's dormancy forms (empty under v1) and the items the closing
        #: attempt ran.
        self._dormancy = tuple(dormancy)
        self._items = items
        #: T05b spec §7.8 (ii) as amended: the opening fixed point's pass order (v2).
        self._order = tuple(order)
        #: T05b spec §6.2 step 3 as amended: each split's temperature columns (v2).
        self._temperatures = temperatures or {}
        #: T05b spec §6.2 as amended: the PH closures the attempt's screen asked, by exact input.
        self._memo = memo
        self.declared_phases: Mapping[str, str] = {
            form.item: form.declared for form in self._dormancy
        }
        _units_and_items_disjoint(self._splits, self._dormancy)

    def _signature(
        self, regimes: Mapping[str, Regime], state: Mapping[str, float]
    ) -> AttemptSignature:
        """The lifted regimes, then the items of the opening `state` (T05b spec §7.8 (i))."""
        lifted = tuple((split.unit, regimes[split.unit]) for split in self._splits)
        return (*lifted, *_items(self._dormancy, state))

    def _settled(
        self,
        state: Mapping[str, float],
        regimes: Mapping[str, Regime],
        fallbacks: Sequence[tuple[str, str]] = (),
    ) -> tuple[dict[str, float], dict[str, Regime], tuple[tuple[str, str], ...]]:
        """T05b spec §7.8 (ii) as amended (Q-S9, R-065): a restart opening made consistent with
        exact dormancy — every lifted split's `ZERO_FLOW` membership and every item, to a fixed
        point (`_settle`), the closing attempt's items the reference. Returns the opening and F2's
        records (§6.5) of the kernel answers the caller set (`fallbacks`) and of each split the
        fixed point took out of `ZERO_FLOW` (`fallback(<U>, tp)` for a PH-type one), in signature
        order; a split the fixed point changed keeps only its own record. Under v1 the opening is
        returned as given (no `ZERO_FLOW`, no forms)."""
        if not self._v2:
            return dict(state), dict(regimes), tuple(fallbacks)
        opened, settled, records, changes = _settle(
            state, regimes, order=self._order, reference=self._items, leave=self._leave
        )
        merged = dict(fallbacks)
        for change in changes:
            merged.pop(change.split.unit, None)
        merged.update(records)
        ordered = tuple(
            (split.unit, merged[split.unit]) for split in self._splits if split.unit in merged
        )
        return opened, settled, ordered

    def _leave(self, split: LiftedSplit, state: Mapping[str, float]) -> _KernelAnswer:
        """§7.4's leaving: regime and split from the TP flash at `state`, `tp` for PH-type (at
        the feed's `T`, written to the split's temperature columns, as amended by Q-S14)."""
        return _contract_kernel(
            self._provider,
            self._context,
            split,
            state,
            self._ph_units,
            v2=True,
            regime="ZERO_FLOW",
            temperatures=self._temperatures.get(split.unit),
        )

    def _answer(self, split: LiftedSplit, state: Mapping[str, float]) -> _KernelAnswer:
        return _contract_kernel(
            self._provider,
            self._context,
            split,
            state,
            self._ph_units,
            v2=self._v2,
            regime=self._regimes[split.unit],
            temperatures=self._temperatures.get(split.unit),
            memo=self._memo,
        )

    def _projected(
        self, state: Mapping[str, float], unit: str, known: _KernelAnswer | None = None
    ) -> tuple[dict[str, float], dict[str, Regime], tuple[tuple[str, str], ...]]:
        """The state with `unit`'s split from the kernel (`known`, when the caller already asked
        it at this state), the regimes it opens under, and F2's record for it (§6.5)."""
        split = next(entry for entry in self._splits if entry.unit == unit)
        answer = known if known is not None else self._answer(split, state)
        opened, regimes = dict(state), dict(self._regimes)
        opened.update(answer.values)
        regimes[unit] = answer.regime
        return self._settled(opened, regimes, ((unit, answer.fallback),) if answer.fallback else ())

    def converged(self, result: NewtonResult) -> Conversion | None:
        """§4.7(a), by the branch found; the first inadmissible unit restarts in the kernel's."""
        for split in self._splits:
            branch = _branch_found(split, self._end)
            ok, value = _admissible(
                self._provider,
                self._context,
                split,
                branch,
                self._end,
                self._policy.admissibility_epsilon,
            )
            if not ok:
                opened, regimes, fallbacks = self._projected(self._end, split.unit)
                label = INADMISSIBLE_BRANCH[branch]
                return Conversion(
                    signature=self._signature(regimes, opened),
                    opening=(opened, regimes),
                    source="closure_projection",
                    cause=f"inadmissible({split.stream}, {label})",
                    observations={f"admissibility:{split.stream}": value},
                    fallbacks=fallbacks,
                )
        return self._items_disagree()

    def _items_disagree(self) -> Conversion | None:
        """T05b spec §7.8 (iv) 1: an item whose trigger streams flow, or an outlet without one
        whose trigger streams are exactly dormant, restarts with the item toggled. Unreachable
        after the openings and the screen, which compares an empty signature too (§7.8 (iii),
        `newton.another_signature`); specified so that no silent path exists."""
        for form in self._dormancy:
            dormant = _trigger_dormant(form, self._end)
            if dormant == (form.item in self._items):
                continue
            opened, regimes, fallbacks = self._settled(self._end, self._regimes)
            return Conversion(
                signature=self._signature(regimes, opened),
                opening=(opened, regimes),
                source="closure_projection",
                cause=f"inadmissible({form.outlet}, {'dormant' if dormant else 'zero_flow'})",
                fallbacks=fallbacks,
            )
        return None

    def blocked(self, result: NewtonResult) -> Conversion | None:
        """§4.6: `BOUND_BLOCKED` on a watched variable of a `TWO_PHASE` unit — the phase left."""
        watched = _watched_variables(self._splits, self._regimes, self._end)
        found = next((watched[name] for name in result.blocked_by if name in watched), None)
        if found is None:
            return None
        unit, phase, variable = found
        split = next(entry for entry in self._splits if entry.unit == unit)
        remaining: Regime = "LIQUID" if phase == "vapor" else "VAPOR"
        opened, regimes = dict(self._end), dict(self._regimes)
        _pin(opened, split, remaining)
        regimes[unit] = remaining
        opened, regimes, fallbacks = self._settled(opened, regimes)
        return Conversion(
            signature=self._signature(regimes, opened),
            opening=(opened, regimes),
            source="pinned_iterate",
            cause=f"phase_disappeared({unit}, {phase}, {variable})",
            fallbacks=fallbacks,
        )

    def kernel_disagrees(self, result: NewtonResult) -> Conversion | None:
        """§4.7(b): the kernel's regime at the end state (the last accepted iterate)."""
        for split in self._splits:
            answer = self._answer(split, self._end)
            if answer.regime != self._regimes[split.unit]:
                # The TP flash is asked again for the opening, as v1 always has; a PH closure (up
                # to ~3 000 provider calls on its band route, W0.6) is not asked twice.
                known = answer if split.unit in self._ph_units else None
                opened, regimes, fallbacks = self._projected(self._end, split.unit, known)
                return Conversion(
                    signature=self._signature(regimes, opened),
                    opening=(opened, regimes),
                    source="closure_projection",
                    cause=f"kernel_disagrees({split.unit}, {answer.regime})",
                    fallbacks=fallbacks,
                )
        return None

    def at_candidate(self, candidate: Candidate, cause: str) -> Conversion:
        """§4.5: the candidate's full state, each changed unit's split from the kernel there."""
        opened = dict(self._end)
        opened.update(zip(self._free, (float(value) for value in candidate.x), strict=True))
        # T05b spec §7.8 (iii): the screen read the candidate's items off this same state; checked,
        # as the split regimes below are. The opening's own items are recomputed after the lifted
        # part is set (§7.8 (ii)), and may differ from these (an upstream split the kernel sets).
        reported = tuple(entry for entry in candidate.signature if entry[0] not in self._regimes)
        if _items(self._dormancy, opened) != reported:
            raise RuntimeError(
                f"defect: the items at the candidate are {_items(self._dormancy, opened)}, the "
                f"screen reported {reported} (iteration {candidate.iteration}, halving "
                f"{candidate.halving})"
            )
        # T05b spec §7.8 (ii) 5 (ruling Q-S12, both literals): every changed unit's kernel is
        # asked at the candidate itself, and only then are the answers written. Writing each
        # answer before asking the next unit would ask a split whose feed an earlier answer had
        # rewritten (a products-style split's products are the next flash's feed) at a state the
        # screen never saw (re-review M2). Each answer writes only its own split's columns, so the
        # writes are disjoint and their order is immaterial; the lag this leaves between a
        # downstream split's products and its rewritten feed sits on linear mole rows.
        answers: list[tuple[str, _KernelAnswer]] = []
        for unit, regime in candidate.signature:
            if unit not in self._regimes:
                continue
            if regime != self._regimes[unit]:
                split = next(entry for entry in self._splits if entry.unit == unit)
                # The kernel's regime equals the candidate's by construction: the screen took
                # the candidate's reported regime from this same kernel at this same state — or,
                # for a PH-type split, from the band's end enthalpies, which name the regime of
                # every `ok` closure (T05b spec §6.2 as amended). Checked, not assumed (review N4):
                # otherwise the cause and the new signature would disagree. The one sanctioned
                # difference: a flowing PH-type split's closure refused inside the domain range,
                # and the TP fallback (recorded `tp`) governs the opened signature. It does not
                # cover a leaving answer (Q-S15 (3)): the screen reports that from the same TP
                # flash at the same inputs, so a difference there is a defect.
                answer = self._answer(split, opened)
                sanctioned = (
                    split.unit in self._ph_units
                    and answer.fallback == "tp"
                    and self._regimes[unit] != "ZERO_FLOW"
                )
                if answer.regime != regime and not sanctioned:
                    raise RuntimeError(
                        f"defect: the kernel reports {unit} {answer.regime} at the candidate the "
                        f"screen reported {regime} at (iteration {candidate.iteration}, halving "
                        f"{candidate.halving})"
                    )
                answers.append((unit, answer))
        regimes = dict(self._regimes)
        fallbacks: list[tuple[str, str]] = []
        for unit, answer in answers:
            opened.update(answer.values)
            regimes[unit] = answer.regime
            if answer.fallback:
                fallbacks.append((unit, answer.fallback))
        opened, regimes, settled = self._settled(opened, regimes, fallbacks)
        return Conversion(
            signature=self._signature(regimes, opened),
            opening=(opened, regimes),
            source="phase_rejected_trial",
            cause=cause,
            trial=candidate,
            fallbacks=settled,
        )

    def opening_check(self, conversion: Conversion) -> OpeningRefusal | None:
        """§5.1 on the lifted path: pinned variables exactly `+0.0`, every variable finite."""
        state, regimes = conversion.opening
        pinned = tuple(
            name
            for split in self._splits
            for name in _pinned(split, regimes[split.unit], self._forms, self._vapour_only)
        )
        held = set(pinned)
        free = tuple(name for name in self._region.variable_ids if name not in held)
        model_version, constants = self._identity
        requirement = OpeningRequirement(
            signature=conversion.signature,
            model_version=model_version,
            constants_sha256=constants,
            free=free,
            pinned=pinned,
            lower_bounds={
                name: 0.0 for name in free if self._spec.variable_kinds.get(name) == "molar_flow"
            },
        )
        return check_opening(
            OpeningState(values=state, model_version=model_version, constants_sha256=constants),
            requirement,
        )
