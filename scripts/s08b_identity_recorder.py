"""S08b gate G1, family B's recorder (design note `docs/derivations/S08b-design.md` §9 G1). S08b.

A pytest plugin (`-p s08b_identity_recorder`) that `scripts/s08b_identity.py` loads into every
shard of the whole-suite run, in both trees. It wraps `phase_contract.decide` (and rebinds the
modules that imported it by name: `attempts`, `region`) and logs, per call, keyed by
`<test node id>#<call index within the test>`:

- a SHA-256 over the structural fields: the decision's `kind` and `outcome`, and its conversion's
  `signature`, `source`, `fallbacks`, trial `(iteration, halving, alpha.hex())` or `None`, and the
  SHA-256 of its opening state — a `(state, regimes)` pair as its sorted ids with `float.hex`
  values plus its sorted regimes, a vector as its `float.hex` values; a raise is its type and
  message;
- the decision's `message` and `cause`, verbatim (the gate compares them by §9 G1's rule).

The calls of one shard and its pytest exit status are written at the session's end to
`$S08B_IDENTITY_OUT`. A call outside any test (collection, a session fixture before its first
test) is keyed `<outside shard $S08B_IDENTITY_SHARD>`. The plugin refuses to run when
`openflowsheet` is not imported from `$S08B_IDENTITY_TREE`. Gate machinery, not a test.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import numpy as np
import pytest

_CALLS: dict[str, int] = {}
_RECORDS: dict[str, list[str]] = {}


def _hash(fields: Any) -> str:
    return hashlib.sha256(repr(fields).encode()).hexdigest()


def _hex(value: Any) -> str:
    try:
        return float(value).hex()
    except (TypeError, ValueError):
        return repr(value)


def opening_sha256(opening: Any) -> str:
    """§9 G1: a `(state, regimes)` pair by sorted ids and `float.hex` values plus the regimes; a
    vector by its `float.hex` values; anything else by its `repr`."""
    if (
        isinstance(opening, tuple)
        and len(opening) == 2
        and isinstance(opening[0], Mapping)
        and isinstance(opening[1], Mapping)
    ):
        state, regimes = opening
        fields: Any = (
            tuple((name, _hex(state[name])) for name in sorted(state)),
            tuple(sorted((str(unit), str(regime)) for unit, regime in regimes.items())),
        )
    elif opening is None:
        fields = None
    else:
        try:
            vector = np.asarray(opening, dtype=np.float64).ravel()
        except (TypeError, ValueError):
            fields = ("repr", repr(opening))
        else:
            fields = tuple(float(value).hex() for value in vector)
    return _hash(fields)


def structure(decision: Any) -> tuple[Any, ...]:
    """The structural fields of one decision (§9 G1 family B), message and cause excluded."""
    conversion = decision.conversion
    if conversion is None:
        converted: Any = None
    else:
        trial = conversion.trial
        converted = (
            tuple((str(unit), str(regime)) for unit, regime in conversion.signature),
            conversion.source,
            tuple(tuple(pair) for pair in conversion.fallbacks),
            None if trial is None else (trial.iteration, trial.halving, float(trial.alpha).hex()),
            opening_sha256(conversion.opening),
        )
    return (decision.kind, decision.outcome, converted)


def _key() -> str:
    test = os.environ.get("PYTEST_CURRENT_TEST")
    if test is None:
        test = f"<outside shard {os.environ.get('S08B_IDENTITY_SHARD', '?')}>"
    else:
        test = test.rsplit(" ", 1)[0]  # drop the phase: `(setup)`, `(call)`, `(teardown)`
    index = _CALLS[test] = _CALLS.get(test, -1) + 1
    return f"{test}#{index}"


def _install() -> None:
    from openflowsheet.orchestrator import attempts, phase_contract, region  # noqa: F401

    original: Callable[..., Any] = phase_contract.decide

    @functools.wraps(original)
    def recorded(*args: Any, **kwargs: Any) -> Any:
        key = _key()
        try:
            decision = original(*args, **kwargs)
        except Exception as error:
            _RECORDS[key] = [_hash(("raised", type(error).__name__, str(error))), "", ""]
            raise
        _RECORDS[key] = [_hash(structure(decision)), decision.message, decision.cause]
        return decision

    for module in list(sys.modules.values()):  # `phase_contract` and its importers by name
        if getattr(module, "decide", None) is original:
            module.decide = recorded  # type: ignore[attr-defined]


def pytest_configure(config: pytest.Config) -> None:
    import openflowsheet

    tree = Path(os.environ["S08B_IDENTITY_TREE"]).resolve()
    if not Path(openflowsheet.__file__).resolve().is_relative_to(tree):
        raise pytest.UsageError(
            f"openflowsheet is imported from {openflowsheet.__file__}, not {tree}"
        )
    _install()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    out = Path(os.environ["S08B_IDENTITY_OUT"])
    out.write_text(json.dumps({"exit": int(exitstatus), "records": _RECORDS}, sort_keys=True))
