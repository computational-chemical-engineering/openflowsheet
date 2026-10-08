"""The runtime data the package reads, resolved through `importlib.resources` (T08 W4.2).

The package reads three kinds of file it does not generate: the published schemas
(`schemas/*.schema.json`, the application contract and the solution-state check), K04's
registered numerical policy (`benchmarks/k04/reference_values.yaml`, ADR 0007 D2) and T08's
(`benchmarks/t08/numerical_policy_v2.yaml`, ADR 0025), and SYN-001's registered variants
(`benchmarks/syn001/reference_values.yaml`, the CLI's `solve <case>`), and since M01 the five C1
component records the provider `pr-c1-v1` reads (`benchmarks/m01/components.yaml`, M01 spec §3).
Each has
exactly one copy in the repository, at the path its registration names. Until T08 they were found
by walking up from a module's `__file__` to the repository root, which an installed wheel does
not have (T08 release spec §12 Q1, FD5): `openflowsheet solve SYN-001-nominal` from a wheel
failed on import of `run/compare.py`, because the policy was not on disk.

`_data/` inside the package mirrors the repository paths with **symbolic links** to those single
copies — `_data/schemas` → `schemas/`, `_data/benchmarks/k04/reference_values.yaml` →
`benchmarks/k04/reference_values.yaml`, and the same for `syn001` — and `pyproject.toml` declares
them package data. A source checkout and an editable install read the repository's files through
the links; the sdist and the wheel carry the files' bytes, which the T08.A43 build check compares
with the repository's file by file. No content, `$id` or identity-bearing byte is copied by hand
or changed, so there is still one copy and no rumour (`run/compare.py`'s rule).
"""

from __future__ import annotations

from importlib.resources import files
from importlib.resources.abc import Traversable
from typing import Final

__all__ = ["PACKAGED", "packaged"]

#: The repository paths the package carries, each a file or (`schemas`) a directory of them.
PACKAGED: Final[tuple[str, ...]] = (
    "schemas",
    "benchmarks/k04/reference_values.yaml",
    "benchmarks/syn001/reference_values.yaml",
    "benchmarks/t08/numerical_policy_v2.yaml",
    "benchmarks/m01/components.yaml",
)


def packaged(relative: str) -> Traversable:
    """The packaged copy of the repository file or directory `relative` (one of `PACKAGED`, or a
    file inside `schemas`), as a `Traversable` that reads the same bytes in a checkout and in an
    installed wheel."""
    top = relative if relative in PACKAGED else relative.rsplit("/", 1)[0]
    if top not in PACKAGED:
        raise KeyError(f"{relative!r} is not runtime data the package carries; see PACKAGED")
    return files("openflowsheet").joinpath("_data", *relative.split("/"))
