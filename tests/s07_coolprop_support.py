"""S07 (spec §17.4, R-624): the one helper every test that needs CoolProp calls.

CoolProp is the `coolprop` extra, installed in CI's `check` job and in development environments
from `requirements-coolprop.lock`; the `default-install` job and the RC jobs do not have it.
Where it is absent, or is not 8.0.0, the test skips with `ABSENT_REASON`. With
`OPENFLOWSHEET_REQUIRE_COOLPROP=1` (CI's `check` job) the same condition fails the test instead,
so a silent skip cannot hide in CI: the `OPENFLOWSHEET_REQUIRE_BROWSER` pattern of M06 WO-11.
"""

from __future__ import annotations

import importlib
import os
from typing import Final

import pytest

REQUIRE_VARIABLE: Final[str] = "OPENFLOWSHEET_REQUIRE_COOLPROP"
PINNED_VERSION: Final[str] = "8.0.0"
ABSENT_REASON: Final[str] = (
    "CoolProp 8.0.0 is not installed: "
    "python -m pip install --no-deps --require-hashes -r requirements-coolprop.lock"
)


def require_coolprop() -> None:
    """Return when `import CoolProp` succeeds at 8.0.0; otherwise skip, or fail under the flag."""
    try:
        present = importlib.import_module("CoolProp").__version__ == PINNED_VERSION
    except ImportError:
        present = False
    if present:
        return
    if os.environ.get(REQUIRE_VARIABLE) == "1":
        pytest.fail(ABSENT_REASON)
    pytest.skip(ABSENT_REASON)
