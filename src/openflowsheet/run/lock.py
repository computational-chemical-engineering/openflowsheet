"""The packaged lock, verified against the installed runtime closure (X05, ADR 0069 D2, D3, D5).

ADR 0007 D6 records "the lock-file hash" so that two runs can say whether their dependency sets
are the same. Before X05 the hash was recorded whenever a checkout's `requirements.lock` existed,
whatever was installed, and an installed package recorded `""` (R-140). From X05 on the package
carries its lock (`openflowsheet/_data/requirements.lock`, the same bytes in a checkout and a
wheel), and `lock_sha256` is recorded only when each distribution of the registered runtime
closure is installed at exactly the version the lock pins. Otherwise it is `""`, and the failing
distributions are carried as findings that replay names in its reason.

**What is checked is the closure, not the lock.** The lock is the development environment's
freeze (`pytest`, `ruff`, `mcp`, …); a clean install of the wheel has none of those, so checking
every line would make an installed package unverifiable (ADR 0069 §4). Lines outside the closure
are hashed and not checked; installed distributions outside the closure are not looked at.

**Versions compare as strings.** `2.2.4.0` is PEP 440-equal to `2.2.4`, and `==2.2.4` admits
`2.2.4+local`, another build; exact strings are stricter and need no `packaging` at run time.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import re
from collections.abc import Callable
from typing import Final

__all__ = [
    "PACKAGED_LOCK_WHERE",
    "RUNTIME_CLOSURE",
    "TEMPLATES",
    "installed_version",
    "verify_lock",
]

#: ADR 0069 D3: the transitive closure of `[project].dependencies` without extras, measured on
#: Python 3.13 on both registered Linux architectures, by PEP 503 name, in the registered order
#: (the order findings are reported in). A constant, not computed at run time: computing it needs
#: `packaging` and the project's own installed metadata, which a checkout may lack or have stale.
#: `tests/test_x05_lock.py` (X05.A10) measures it against this tuple.
RUNTIME_CLOSURE: Final[tuple[str, ...]] = (
    "attrs",
    "casadi",
    "jsonschema",
    "jsonschema-specifications",
    "numpy",
    "pyyaml",
    "referencing",
    "rpds-py",
    "scipy",
)

#: ADR 0069 D1.2: the label of the packaged lock in a finding (a fixed string, never a path).
PACKAGED_LOCK_WHERE: Final = "openflowsheet/_data/requirements.lock"

#: ADR 0069 D5's findings (F1-F6) and the reasons of `decide_mode`'s unknown-lock branch.
TEMPLATES: Final[dict[str, str]] = {
    "F1": "the lock {where} is missing or unreadable",
    "F2": "the lock {where} is malformed at line {line}: {text}",
    "F3": "{name} is not installed, the lock pins {locked}",
    "F4": "{name} is {installed}, the lock pins {locked}",
    "F5": "{name} is in the runtime closure but not in the lock",
    "F6": "{name}'s installed metadata could not be read: {error}",
    "R_ARCHIVE": (
        "the dependency set is unknown on the archive's side: the archive recorded no verified "
        "lock, so nothing is known to match"
    ),
    "R_THIS": (
        "the dependency set is unknown on this side: this side's lock did not verify ({findings})"
    ),
    "R_BOTH": (
        "the dependency set is unknown on both sides: the archive recorded no verified lock, and "
        "this side's lock did not verify ({findings}); two unknowns are not a match"
    ),
    "NONE": "no verification recorded",
    "JOIN": "; ",
}

#: D2.2: one pin per line, `NAME==VERSION`, after the comment and surrounding blanks are removed.
_PIN: Final = re.compile(
    r"([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)==([A-Za-z0-9][A-Za-z0-9.+!_-]*)"
)
_SEPARATORS: Final = re.compile(r"[-_.]+")


def _normalise(name: str) -> str:
    """PEP 503: runs of `-`, `_`, `.` become one `-`, lower case. For the comparison only."""
    return _SEPARATORS.sub("-", name).lower()


def _pins(text: str, where: str) -> dict[str, str] | str:
    """The lock's pins by normalised name, or the F2 finding at its first malformed line."""
    pins: dict[str, str] = {}
    for number, line in enumerate(text.split("\n"), 1):
        body = line.split("#", 1)[0].strip()
        if not body:
            continue
        match = _PIN.fullmatch(body)
        if match is None or _normalise(match.group(1)) in pins:
            return TEMPLATES["F2"].format(where=where, line=number, text=repr(line))
        pins[_normalise(match.group(1))] = match.group(2)
    return pins


def verify_lock(
    data: bytes | None, installed: Callable[[str], str | None], where: str
) -> tuple[str, tuple[str, ...]]:
    """ADR 0069 D2: `(sha256 of data, ())` if every closure member is installed at its pin, else
    `("", findings)`. Pure, and it never raises: a read that raises is itself a finding (F6).

    Every member is checked, in `RUNTIME_CLOSURE`'s order; nothing short-circuits, so a replay
    reason names every failing distribution. The hash is of the bytes as read, comments, blank
    lines and the lines outside the closure included.
    """
    if data is None:
        return "", (TEMPLATES["F1"].format(where=where),)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return "", (TEMPLATES["F1"].format(where=where),)
    pins = _pins(text, where)
    if isinstance(pins, str):
        return "", (pins,)
    findings: list[str] = []
    for name in RUNTIME_CLOSURE:
        locked = pins.get(name)
        if locked is None:
            findings.append(TEMPLATES["F5"].format(name=name))
            continue
        try:
            found = installed(name)
        except Exception as error:  # noqa: BLE001 - D2.3: a read that raises is a finding
            findings.append(TEMPLATES["F6"].format(name=name, error=type(error).__name__))
            continue
        if found is None:
            findings.append(TEMPLATES["F3"].format(name=name, locked=locked))
        elif found != locked:
            findings.append(TEMPLATES["F4"].format(name=name, installed=found, locked=locked))
    if findings:
        return "", tuple(findings)
    return hashlib.sha256(data).hexdigest(), ()


#: D6: each name's outcome, read once per process — the version, `None` (not installed), or what
#: the read raised (re-raised as is, so its class is the one a finding names). Idempotent, so two
#: threads racing on a name write equivalent values.
_INSTALLED: dict[str, str | None | Exception] = {}


def installed_version(name: str) -> str | None:
    """The version `importlib.metadata` reports for distribution `name`, or `None` if none is found.

    A distribution found with no non-empty `Version` raises `TypeError` (so the finding names
    `TypeError` whatever the Python's own behaviour; ADR 0069 D2). Any other exception of the
    read propagates, for `verify_lock` to report. The outcome is memoised per process (D6): the
    reads are the expensive part of `environment()`, the lock itself is re-read every call.
    """
    if name not in _INSTALLED:
        outcome: str | None | Exception
        try:
            version = importlib.metadata.distribution(name).metadata.get("Version")
        except importlib.metadata.PackageNotFoundError:
            outcome = None
        except Exception as error:  # noqa: BLE001 - memoised, re-raised below
            outcome = error
        else:
            outcome = (
                version
                if isinstance(version, str) and version
                else TypeError(f"{name} is installed with no Version in its metadata")
            )
        _INSTALLED[name] = outcome
    outcome = _INSTALLED[name]
    if isinstance(outcome, Exception):
        raise outcome
    return outcome
