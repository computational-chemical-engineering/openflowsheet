"""The runtime data the package reads, resolved through `importlib.resources` (T08 W4.2).

The package reads four kinds of file it does not generate: the published schemas
(`schemas/*.schema.json`, the application contract and the solution-state check), K04's
registered numerical policy (`benchmarks/k04/reference_values.yaml`, ADR 0007 D2) and T08's
(`benchmarks/t08/numerical_policy_v2.yaml`, ADR 0025), SYN-001's registered variants
(`benchmarks/syn001/reference_values.yaml`, the CLI's `solve <case>`), and the diagnostic web
shell's static files (`apps/web/`, served by `serve-http --ui`; M06, ADR 0030 D2). Each has
exactly one copy in the repository, at the path its registration names. Until T08 they were found
by walking up from a module's `__file__` to the repository root, which an installed wheel does
not have (T08 release spec §12 Q1, FD5): `openflowsheet solve SYN-001-nominal` from a wheel
failed on import of `run/compare.py`, because the policy was not on disk.

`_data/` inside the package mirrors the repository paths with **symbolic links** to those single
copies — `_data/schemas` → `schemas/`, `_data/benchmarks/k04/reference_values.yaml` →
`benchmarks/k04/reference_values.yaml`, and the same for `syn001` — and `pyproject.toml` declares
them package data. One link's package path is not its repository path: `_data/web` → `apps/web/`
(blueprint §15 puts the web client under `apps/`), recorded in `REPOSITORY_PATHS`. A source checkout and an editable install read the repository's files through
the links; the sdist and the wheel carry the files' bytes, which the T08.A43 build check compares
with the repository's file by file. No content, `$id` or identity-bearing byte is copied by hand
or changed, so there is still one copy and no rumour (`run/compare.py`'s rule).
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
from importlib.resources.abc import Traversable
from types import MappingProxyType
from typing import Final

__all__ = ["DIRECTORIES", "PACKAGED", "REPOSITORY_PATHS", "packaged", "repository_path"]

#: The paths below `_data/` the package carries, each a file or a directory of them.
PACKAGED: Final[tuple[str, ...]] = (
    "schemas",
    "benchmarks/k04/reference_values.yaml",
    "benchmarks/syn001/reference_values.yaml",
    "benchmarks/t08/numerical_policy_v2.yaml",
    "web",
)
#: The entries of `PACKAGED` that are directories: a file anywhere below one is packaged too.
DIRECTORIES: Final[tuple[str, ...]] = ("schemas", "web")
#: The repository path of each packaged path that does not sit at the same path in the repository.
REPOSITORY_PATHS: Final[Mapping[str, str]] = MappingProxyType({"web": "apps/web"})


def repository_path(relative: str) -> str:
    """Where the single repository copy of the packaged path `relative` (one of `PACKAGED`) lives,
    relative to the repository root."""
    if relative not in PACKAGED:
        raise KeyError(f"{relative!r} is not runtime data the package carries; see PACKAGED")
    return REPOSITORY_PATHS.get(relative, relative)


def packaged(relative: str) -> Traversable:
    """The packaged copy of the file or directory `relative` below `_data/` (one of `PACKAGED`, or
    a file below one of `DIRECTORIES`), as a `Traversable` that reads the same bytes in a checkout
    and in an installed wheel."""
    if relative not in PACKAGED and not any(
        relative.startswith(f"{directory}/") for directory in DIRECTORIES
    ):
        raise KeyError(f"{relative!r} is not runtime data the package carries; see PACKAGED")
    return files("openflowsheet").joinpath("_data", *relative.split("/"))
