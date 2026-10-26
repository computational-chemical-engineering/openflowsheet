"""S08b design-time probe: a pytest plugin (`-p s08b_probe`), NOT production code, NOT a test.

Modes, by the environment variable `S08B_MODE` (records go to `$S08B_OUT/<mode>-<pid>.jsonl`):

- `observe` changes nothing. It logs
  (M1) every call of the contract's `_proposal` in which the `"."` heuristic (`_is_item`) and the
  explicit rule (an item is a key of the attempt's `declared_phases`) classify a signature entry
  differently, and, where `_proposal` would consult the restart selection, the candidate each rule
  chooses and the `phase_wall` change list each writes;
  (S1) every lifted split whose branch found is `TWO_PHASE` at an accepted closure
  (`_LiftedOps.converged` returned `None`): its flows, its saturation errors
  `T - T_bub(liquid)` and `T - T_dew(vapour)` (`band_temperature`), and the raw provider's TP
  flash of its feed at `(T, P)`;
  (S2) every raw-provider TP flash answer that is `TWO_PHASE` with a minority phase fraction
  below 1e-6.
  Extra property calls go to the innermost provider (below the budget and cache wrappers) and
  only for the four known raw provider classes, so no budget, cache or counter is touched.
- `fix` substitutes the design's rule: while `_proposal` runs, `_is_item(key)` is
  `key in declared_phases`. Nothing is logged.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Mapping
from typing import Any

import openflowsheet.orchestrator.phase_contract as pc
import openflowsheet.orchestrator.region as region
from openflowsheet.models.syn001.cascade_solve import DECLARATION_CONTEXT
from openflowsheet.models.syn001.saturation_band import band_temperature
from openflowsheet.thermo import FlashRequest, StreamState
from openflowsheet.thermo.coolprop_heos import CoolPropHeosProvider
from openflowsheet.thermo.pr_lib import PrLibProvider
from openflowsheet.thermo.syn001 import Syn001Provider
from openflowsheet.thermo.wilson_ig import WilsonIdealGasProvider

MODE = os.environ.get("S08B_MODE", "observe")
OUT = os.environ.get("S08B_OUT", ".")
RAW = (Syn001Provider, PrLibProvider, WilsonIdealGasProvider, CoolPropHeosProvider)
NEAR_TRIVIAL = 1e-6
_ORIGINAL_PROPOSAL = pc._proposal
#: `None` once S08b has removed the heuristic; M1 is then skipped.
_ORIGINAL_IS_ITEM = getattr(pc, "_is_item", None)
#: Set while S1 asks the raw provider, so its own calls are not S2 records.
_QUIET = [False]


def _log(record: Mapping[str, Any]) -> None:
    test = os.environ.get("PYTEST_CURRENT_TEST", "").rsplit(" ", 1)[0]
    with open(os.path.join(OUT, f"{MODE}-{os.getpid()}.jsonl"), "a") as sink:
        sink.write(json.dumps({"test": test, **record}, default=repr) + "\n")


class _Explicit:
    """`_is_item` swapped for `key in declared` for the duration of a `with` block."""

    def __init__(self, declared: Mapping[str, str]) -> None:
        self.items = frozenset(declared)

    def __enter__(self) -> None:
        pc._is_item = self.items.__contains__

    def __exit__(self, *_: object) -> None:
        pc._is_item = _ORIGINAL_IS_ITEM


def _proposal_fixed(result: Any, frozen: Any, wall: Any, ops: Any) -> Any:
    with _Explicit(getattr(ops, "declared_phases", {})):
        return _ORIGINAL_PROPOSAL(result, frozen, wall, ops)


def _consulted(result: Any, wall: Any) -> bool:
    """Whether `_proposal` would reach `wall.choose` (rows 2 and 4 of T03 §4.8)."""
    if not wall.candidates:
        return False
    if result.outcome == "PHASE_UPDATE_REQUIRED":
        return True
    return result.outcome in pc._STALL_OUTCOMES and wall.stalled_at_the_wall(
        result.outcome, result.iterations
    )


def _compact(signature: Any) -> str:
    return "".join(regime[0] for _, regime in signature)


def _proposal_observed(result: Any, frozen: Any, wall: Any, ops: Any) -> Any:
    declared: Mapping[str, str] = getattr(ops, "declared_phases", {})
    items = frozenset(declared)
    signatures = [frozen, *(candidate.signature for candidate in wall.candidates)]
    keys = {key for signature in signatures for key, _ in signature}
    disagree = sorted(key for key in keys if ("." in key) != (key in items))
    if disagree:
        record: dict[str, Any] = {
            "kind": "M1",
            "outcome": result.outcome,
            "lifted": bool(ops.lifted),
            "disagree": len(disagree),
            "sample": disagree[:2],
            "frozen": _compact(frozen),
            "candidates": [(c.halving, c.alpha, _compact(c.signature)) for c in wall.candidates],
            "consulted": _consulted(result, wall),
        }
        if record["consulted"]:
            old = wall.choose(frozen)
            old_changes = pc._changes(frozen, old.signature, declared)
            with _Explicit(declared):
                new = wall.choose(frozen)
                new_changes = pc._changes(frozen, new.signature, declared)
            record.update(
                old_index=wall.candidates.index(old),
                new_index=wall.candidates.index(new),
                old_changes=old_changes,
                new_changes=new_changes,
            )
        _log(record)
    return _ORIGINAL_PROPOSAL(result, frozen, wall, ops)


def _raw(provider: Any) -> Any:
    while hasattr(provider, "_provider"):
        provider = provider._provider
    return provider if isinstance(provider, RAW) else None


def _saturation(raw: Any, flows: tuple[float, ...], pressure: float, beta: float) -> Any:
    if not any(value > 0.0 for value in flows):
        return None
    try:
        band = band_temperature(raw, flows, pressure, beta, DECLARATION_CONTEXT)
    except Exception as error:  # a probe records a refusal, it does not stop
        return f"refused: {type(error).__name__}"
    if band.position != "inside" or band.temperature is None:
        return f"position: {band.position}"
    return band.temperature


_ORIGINAL_CONVERGED = region._LiftedOps.converged


def _converged_observed(self: Any, result: Any) -> Any:
    answer = _ORIGINAL_CONVERGED(self, result)
    if answer is not None:
        return answer
    raw = _raw(self._provider)
    state = self._end
    _QUIET[0] = True
    try:
        _record_two_phase(self, raw, state)
    finally:
        _QUIET[0] = False
    return answer


def _record_two_phase(self: Any, raw: Any, state: Mapping[str, float]) -> None:
    for split in self._splits:
        if region._branch_found(split, state) != "TWO_PHASE":
            continue
        temperature, pressure = float(state[split.temperature]), float(state[split.pressure])
        vapour = tuple(float(state[name]) for name in split.vapor)
        liquid = tuple(float(state[name]) for name in split.liquid)
        feed = tuple(float(state[name]) for name in split.feed)
        record: dict[str, Any] = {
            "kind": "S1",
            "unit": split.unit,
            "provider": type(raw).__name__ if raw is not None else "wrapped",
            "V": float(state[split.vapor_total]),
            "L": float(state[split.liquid_total]),
            "n": math.fsum(feed),
            "T": temperature,
        }
        if raw is not None:
            bubble = _saturation(raw, liquid, pressure, 0.0)
            dew = _saturation(raw, vapour, pressure, 1.0)
            record["bubble_error"] = temperature - bubble if isinstance(bubble, float) else bubble
            record["dew_error"] = temperature - dew if isinstance(dew, float) else dew
            flash = raw.flash(
                FlashRequest(state=StreamState(n=feed, temperature=temperature, pressure=pressure)),
                DECLARATION_CONTEXT,
            )
            record["kernel"] = (flash.status, flash.phase_signature, flash.vapor_fraction)
        _log(record)


def _wrap_flash(cls: Any) -> None:
    original = cls.flash

    def flash(self: Any, request: Any, context: Any) -> Any:
        answer = original(self, request, context)
        fraction = answer.vapor_fraction
        if _QUIET[0]:
            return answer
        if answer.phase_signature == "TWO_PHASE" and fraction is not None:
            minority = min(fraction, 1.0 - fraction)
            if minority < NEAR_TRIVIAL:
                _log(
                    {
                        "kind": "S2",
                        "provider": cls.__name__,
                        "vapor_fraction": fraction,
                        "n": math.fsum(request.state.n),
                        "T": request.state.temperature,
                        "P": request.state.pressure,
                    }
                )
        return answer

    cls.flash = flash


if MODE == "fix":
    pc._proposal = _proposal_fixed
elif MODE == "observe":
    if _ORIGINAL_IS_ITEM is not None:
        pc._proposal = _proposal_observed
    region._LiftedOps.converged = _converged_observed
    for provider_class in RAW:
        _wrap_flash(provider_class)
