"""One BLAS thread for the surrogate fit (M04 spec §20 A3.3, register R-362; build decision E36).

The fit's SVD, QR, triangular solve and products (`quadratic.fit_quadratic`) run in the OpenBLAS
libraries NumPy and SciPy load — each wheel of the lock bundles its own `scipy_openblas` — and
their last bits depend on the thread count OpenBLAS splits the work over (build log E33: WO-11's
manifest `d65bb022…` at one thread, `908cbe2f…` at eight). The manifest is the surrogate's
identity, so the fit runs under one thread whatever `OPENBLAS_NUM_THREADS`/`OMP_NUM_THREADS` say:
`single_blas_thread` sets every OpenBLAS loaded in the process to one thread through the
library's own API and restores each previous count on exit.

The loaded libraries are found by `_platform.loaded_libraries` (`/proc/self/maps` on Linux, the
dynamic loader's images on macOS, the process's modules on Windows) and opened with
`LOADED_LIBRARY_MODE`, so nothing is loaded that the process had not loaded; each is driven by the
first pair of `<prefix>_get_num_threads<suffix>`/`<prefix>_set_num_threads<suffix>` it exports,
`prefix` in (`scipy_openblas`, `openblas`), `suffix` in (`64_`, ``) — the symbols of the bundled
ILP64 (NumPy) and LP64 (SciPy) builds and of a system OpenBLAS. Where no OpenBLAS is loaded
(another BLAS, such as Accelerate), `controlled()` is empty and the pin is a no-op: OpenBLAS's
thread variables then do not reach the fit, and that BLAS's own thread count (Accelerate's
`VECLIB_MAXIMUM_THREADS`) is not set. m04 a49 varies `VECLIB_MAXIMUM_THREADS` with OpenBLAS's
variables on macOS, so A3.3 is measured there too; a fit that differs with it is an A3.3 finding
(X07a WO9 review W-2). A3.3 is a rule on one platform (A32: "bitwise on one platform, whatever
the thread setting"); spec §18 A1.3's classes govern comparisons across platforms only (X07a
review R-1).

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
from typing import Final

from openflowsheet._platform import LOADED_LIBRARY_MODE, loaded_libraries

__all__ = ["BlasLibrary", "controlled", "single_blas_thread"]

_PREFIXES: Final = ("scipy_openblas", "openblas")
_SUFFIXES: Final = ("64_", "")


@dataclass(frozen=True)
class BlasLibrary:
    """A loaded OpenBLAS and its thread-count accessors."""

    path: str
    get: Callable[[], int]
    set: Callable[[int], None]


def _loaded_openblas() -> list[str]:
    """The paths of the loaded shared objects whose file name names OpenBLAS, sorted."""
    return [path for path in loaded_libraries() if "openblas" in os.path.basename(path).lower()]


def _library(path: str) -> BlasLibrary | None:
    try:
        handle = ctypes.CDLL(path, mode=LOADED_LIBRARY_MODE)
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
    """Every loaded OpenBLAS whose thread count this module can set (empty with another BLAS)."""
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
