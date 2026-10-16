"""One BLAS thread for the surrogate fit (M04 spec §20 A3.3, register R-362; build decision E36).

The fit's SVD, QR, triangular solve and products (`quadratic.fit_quadratic`) run in the OpenBLAS
libraries NumPy and SciPy load — each wheel of the lock bundles its own `scipy_openblas` — and
their last bits depend on the thread count OpenBLAS splits the work over (build log E33: WO-11's
manifest `d65bb022…` at one thread, `908cbe2f…` at eight). The manifest is the surrogate's
identity, so the fit runs under one thread whatever `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS` say:
`single_blas_thread` sets every OpenBLAS loaded in the process to one thread through the
library's own API and restores each previous count on exit.

The loaded libraries are found in `/proc/self/maps` (Linux) and opened with `RTLD_NOLOAD`, so
nothing is loaded that the process had not loaded; each is driven by the first pair of
`<prefix>_get_num_threads<suffix>`/`<prefix>_set_num_threads<suffix>` it exports, `prefix` in
(`scipy_openblas`, `openblas`), `suffix` in (`64_`, ``) — the symbols of the bundled ILP64 (NumPy)
and LP64 (SciPy) builds and of a system OpenBLAS. Where no OpenBLAS is loaded (another BLAS, or a
platform without `/proc`), `controlled()` is empty and the pin is a no-op: the manifest is then
bitwise only at a fixed thread setting (spec §18 A1.3's platform classes govern).

The limit is process-wide, as `threadpoolctl`'s is: at most one job computes per interpreter (the
inline executor's `COMPUTE_LOCK`; the process executor's one worker per job), so no other
computation shares the window.
"""

from __future__ import annotations

import ctypes
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Final

__all__ = ["BlasLibrary", "controlled", "single_blas_thread"]

_PREFIXES: Final = ("scipy_openblas", "openblas")
_SUFFIXES: Final = ("64_", "")
_MAPS: Final = Path("/proc/self/maps")


@dataclass(frozen=True)
class BlasLibrary:
    """A loaded OpenBLAS and its thread-count accessors."""

    path: str
    get: Callable[[], int]
    set: Callable[[int], None]


def _loaded_openblas() -> list[str]:
    """The paths of the loaded shared objects whose file name names OpenBLAS, sorted."""
    try:
        maps = _MAPS.read_text(encoding="utf-8")
    except OSError:
        return []
    paths = set()
    for line in maps.splitlines():
        fields = line.split(None, 5)
        if len(fields) == 6 and "openblas" in os.path.basename(fields[5]).lower():
            paths.add(fields[5].strip())
    return sorted(paths)


def _library(path: str) -> BlasLibrary | None:
    try:
        handle = ctypes.CDLL(path, mode=os.RTLD_NOLOAD | os.RTLD_LAZY)
    except OSError:
        return None
    for prefix in _PREFIXES:
        for suffix in _SUFFIXES:
            get = getattr(handle, f"{prefix}_get_num_threads{suffix}", None)
            put = getattr(handle, f"{prefix}_set_num_threads{suffix}", None)
            if get is not None and put is not None:
                get.restype, get.argtypes = ctypes.c_int, []
                put.restype, put.argtypes = None, [ctypes.c_int]
                return BlasLibrary(path, get, put)
    return None


def controlled() -> tuple[BlasLibrary, ...]:
    """Every loaded OpenBLAS whose thread count this module can set (empty off Linux or with
    another BLAS)."""
    found = (_library(path) for path in _loaded_openblas())
    return tuple(library for library in found if library is not None)


@contextmanager
def single_blas_thread() -> Iterator[tuple[BlasLibrary, ...]]:
    """Run the block with every loaded OpenBLAS at one thread; restore each count on exit."""
    libraries = controlled()
    previous = [library.get() for library in libraries]
    try:
        for library in libraries:
            library.set(1)
        yield libraries
    finally:
        for library, count in zip(libraries, previous, strict=True):
            library.set(count)
