"""S11 gate G1, family C's recorder (design note `docs/derivations/S11-design.md` §6.2 G1). S11.

A pytest plugin (`-p s11_identity_recorder`) that `scripts/s11_identity.py` loads into every shard
of the whole-suite run, in both trees. It wraps `revision_binding.bind_revision_flowsheet` (and
rebinds the modules already loaded that imported it by name) and logs, per call, keyed by
`<test node id>#<call index within the test>`, one SHA-256 over:

- the document's SHA-256 (ADR 0002's `document_sha256`, taken before the call, with the top-level
  revision identifiers `VOLATILE` set to one marker; a document with no canonical form by the
  SHA-256 of its `repr`);
- the outcome: for an `Unbound` its kind, code (`detail`), `implicated` and hint (the hint is not
  part of `Unbound`'s equality, so it is named here); for a `RevisionBinding` whether its
  `revision_sha256` is the unmarked document's `document_sha256`, and its `ProblemSpec`'s ids
  (label, variable, equation, parameter and block ids), kinds (`variable_kinds`, `row_kinds`) and
  parameters (`float.hex`, in `parameter_ids` order); a raise is its type and message.

`VOLATILE`: the binder reads neither field, and a test that commits through the store may name
its revisions by the clock (`test_t07_r6_replays`' `time.monotonic_ns()`), so the raw document,
and the `revision_sha256` taken from it, differ between any two runs of one tree.

The calls of one shard and its pytest exit status are written at the session's end to
`$S11_IDENTITY_OUT`. A call outside any test is keyed `<outside shard $S11_IDENTITY_SHARD>`. The
plugin refuses to run when `openflowsheet` is not imported from `$S11_IDENTITY_TREE`. Gate
machinery, not a test.
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

import pytest

#: The top-level revision identifiers the digest does not read (the binder does not either).
VOLATILE = ("revision_id", "parent_revision")
_MARKER = "<volatile>"
_CALLS: dict[str, int] = {}
_RECORDS: dict[str, str] = {}


def _hash(fields: Any) -> str:
    return hashlib.sha256(repr(fields).encode()).hexdigest()


def _hex(value: Any) -> str:
    try:
        return float(value).hex()
    except (TypeError, ValueError):
        return repr(value)


def _raw_sha256(document: Any) -> str | None:
    from openflowsheet.canonical import document_sha256

    try:
        return document_sha256(document)
    except Exception:  # a non-canonical document is refused typed by the binder, not here
        return None


def document_digest(document: Any) -> str:
    """ADR 0002's `document_sha256` with `VOLATILE` marked, or the SHA-256 of the marked
    document's `repr` when it has no canonical form."""
    if isinstance(document, Mapping):
        document = {key: (_MARKER if key in VOLATILE else value) for key, value in document.items()}
    digest = _raw_sha256(document)
    return _hash(("repr", repr(document))) if digest is None else digest


def _sorted_items(mapping: Mapping[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple((str(key), str(mapping[key])) for key in sorted(mapping))


def outcome(answer: Any, raw_sha256: str | None = None) -> tuple[Any, ...]:
    """§6.2 G1: what one binding outcome is compared by (`raw_sha256`: the unmarked document's
    `document_sha256`)."""
    from openflowsheet.application.binding import Unbound
    from openflowsheet.application.revision_binding import RevisionBinding

    if isinstance(answer, Unbound):
        return ("unbound", answer.kind, answer.detail, tuple(answer.implicated), answer.hint)
    if isinstance(answer, RevisionBinding):
        spec = answer.spec
        return (
            "bound",
            answer.revision_sha256 == raw_sha256,
            spec.label,
            tuple(spec.variable_ids),
            tuple(spec.equation_ids),
            tuple(spec.parameter_ids),
            tuple(block.block_id for block in spec.blocks),
            _sorted_items(spec.variable_kinds),
            _sorted_items(spec.row_kinds),
            tuple((name, _hex(spec.parameters[name])) for name in spec.parameter_ids),
        )
    return ("other", type(answer).__name__, repr(answer))


def _key() -> str:
    test = os.environ.get("PYTEST_CURRENT_TEST")
    if test is None:
        test = f"<outside shard {os.environ.get('S11_IDENTITY_SHARD', '?')}>"
    else:
        test = test.rsplit(" ", 1)[0]  # drop the phase: `(setup)`, `(call)`, `(teardown)`
    index = _CALLS[test] = _CALLS.get(test, -1) + 1
    return f"{test}#{index}"


def _install() -> None:
    from openflowsheet.application import revision_binding

    original: Callable[..., Any] = revision_binding.bind_revision_flowsheet

    @functools.wraps(original)
    def recorded(document: Any, *args: Any, **kwargs: Any) -> Any:
        key = _key()
        digest, raw = document_digest(document), _raw_sha256(document)
        try:
            answer = original(document, *args, **kwargs)
        except Exception as error:
            _RECORDS[key] = _hash((digest, "raised", type(error).__name__, str(error)))
            raise
        _RECORDS[key] = _hash((digest, outcome(answer, raw)))
        return answer

    for module in list(sys.modules.values()):  # `revision_binding` and its importers by name
        if getattr(module, "bind_revision_flowsheet", None) is original:
            module.bind_revision_flowsheet = recorded  # type: ignore[attr-defined]


def pytest_configure(config: pytest.Config) -> None:
    import openflowsheet

    tree = Path(os.environ["S11_IDENTITY_TREE"]).resolve()
    if not Path(openflowsheet.__file__).resolve().is_relative_to(tree):
        raise pytest.UsageError(
            f"openflowsheet is imported from {openflowsheet.__file__}, not {tree}"
        )
    _install()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    out = Path(os.environ["S11_IDENTITY_OUT"])
    out.write_text(json.dumps({"exit": int(exitstatus), "records": _RECORDS}, sort_keys=True))
