"""The runtime data the package reads, resolved through `importlib.resources` (T08 W4.2).

The package reads five kinds of file it does not generate: the published schemas
(`schemas/*.schema.json`, the application contract and the solution-state check), K04's
registered numerical policy (`benchmarks/k04/reference_values.yaml`, ADR 0007 D2) and T08's
(`benchmarks/t08/numerical_policy_v2.yaml`, ADR 0025), SYN-001's registered variants
(`benchmarks/syn001/reference_values.yaml`, the CLI's `solve <case>`), since M01 the five C1
component records the provider `pr-c1-v1` reads (`benchmarks/m01/components.yaml`, M01 spec §3),
since M02 the external addendum whose `compare` rules a coupled replay reads
(`benchmarks/m02/numerical_policy_external.yaml`, register R-317 (b)), since S05 the IAPWS-95
coefficient file the library-only provider `iapws95-v1` reads
(`benchmarks/s05/iapws95_coefficients.json`, R-616; its attribution is in NOTICE), the
diagnostic web shell's static files (`apps/web/`, served by `serve-http --ui`; M06, ADR 0030 D2),
since E01 the assessment data (`assessment/{cost,index,lca}/*.json`: the SSLW cost set, the
capital-chain presets, three index series and two LCA tables, ADR 0052; their attributions are in
NOTICE),
and since 0.3.0 the Wilson records `wilson-ig-v1` and `wilson-ig-v2` read
(`benchmarks/s10/records.yaml`) with the Kurihara 1993 Table II points they are fitted to
(`benchmarks/s10/vle/kurihara1993_binaries.csv`; V03 spec §9.1, R-880; their attribution is in
NOTICE).
Each has exactly one copy in the repository, at the path its registration names. Until T08 they were
found by walking up from a module's `__file__` to the repository root, which an installed wheel does
not have (T08 release spec §12 Q1, FD5): `openflowsheet solve SYN-001-nominal` from a wheel failed
on import of `run/compare.py`, because the policy was not on disk.

`_data/` inside the package mirrors the repository paths with **symbolic links** to those single
copies — `_data/schemas` → `schemas/`, `_data/benchmarks/k04/reference_values.yaml` →
`benchmarks/k04/reference_values.yaml`, and the same for `syn001` — and `pyproject.toml` declares
them package data. One link's package path is not its repository path: `_data/web` → `apps/web/`
(blueprint §15 puts the web client under `apps/`), recorded in `REPOSITORY_PATHS`. A source checkout
and an editable install read the repository's files through the links; the sdist and the wheel carry
the files' bytes, which the T08.A43 build check compares with the repository's file by file. No
content, `$id` or identity-bearing byte is copied by hand or changed, so there is still one copy and
no rumour (`run/compare.py`'s rule).
"""

from __future__ import annotations

from collections.abc import Mapping
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from types import MappingProxyType
from typing import Final

__all__ = [
    "DIRECTORIES",
    "PACKAGED",
    "REPOSITORY_PATHS",
    "packaged",
    "packaged_path",
    "repository_path",
]

#: The paths below `_data/` the package carries, each a file or a directory of them.
PACKAGED: Final[tuple[str, ...]] = (
    "schemas",
    "benchmarks/k04/reference_values.yaml",
    "benchmarks/syn001/reference_values.yaml",
    "benchmarks/t08/numerical_policy_v2.yaml",
    "benchmarks/m01/components.yaml",
    "benchmarks/m02/numerical_policy_external.yaml",
    # S05 (R-616): the IAPWS-95 coefficient file `iapws95-v1` reads; one file entry, so nothing
    # placed beside it later ships (spec S05 §16.2 A26 (a)).
    "benchmarks/s05/iapws95_coefficients.json",
    # E01 (ADR 0052): the assessment data, one file entry each like S05's (a file placed beside them
    # fails T08's package-data check); the third-party ones carry their attribution in NOTICE.
    "assessment/cost/chains.json",
    "assessment/cost/sslw-idaes-v1.json",
    "assessment/index/bls-ppi-wpu11-annual-v1.json",
    "assessment/index/eurostat-ppi-c28-ea-annual-v1.json",
    "assessment/index/frb-g5a-annual-v1.json",
    "assessment/lca/gwp100-ipcc-ar6-v1.json",
    "assessment/lca/test-background-v1.json",
    # V03 (R-880, Frank's Q-F3): Wilson's records and the Table II points of their fit, one file
    # entry each like S05's; the double entries, the RC-06 files and the reports stay out (§9.1).
    "benchmarks/s10/records.yaml",
    "benchmarks/s10/vle/kurihara1993_binaries.csv",
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


def packaged_path(relative: str) -> Path | None:
    """The packaged file `relative` (one of `PACKAGED`) as a path on the file system, for a reader
    that takes a path rather than bytes; `None` where the installed package does not carry it as
    a file on disk (V03 spec §9.1: the binder and the verifier hand Wilson's records to
    `thermo.wilson_ig`, whose own lookup finds a source checkout only)."""
    copy = packaged(relative)
    return copy if isinstance(copy, Path) and copy.is_file() else None
