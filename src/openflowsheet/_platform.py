"""The operating-system calls that differ between POSIX and Windows (X07a, roadmap 0.5).

Three concerns, each a pair of functions, below every layer that uses them:

- **file locks**: `lock_exclusive`, and `release_lock`, `release_lock_file` or `close_locked`: an
  exclusive lock on an open descriptor taken without blocking (`application.store` §9.3 owners,
  `adapters.experiments.store` key locks);
- **process trees**: `isolate_process_tree` in a new worker and `kill_process_tree` in its parent
  (ADR 0033 D2 L2, the forced kill reaches the worker's children);
- **atomic replace**: `replace_file` and `fsync_directory` (`openflowsheet._files`).

On Linux and macOS every function makes the system calls, with the arguments and in the order,
that its callers made before this module existed. Windows gets the documented equivalent:
`msvcrt.locking` on one byte at offset 0 for `flock`; a Job Object for the process group; a
bounded retry of `os.replace` while another process holds the target open, and no directory
`fsync` (a directory cannot be opened there; ADR 0061 N12 "fsync ... on POSIX").
"""

from __future__ import annotations

import errno
import os
import sys
import time
from pathlib import Path
from typing import Final

if sys.platform == "win32":
    import ctypes
    import msvcrt
    from ctypes import wintypes
else:
    import fcntl
    import signal

__all__ = [
    "LOADED_LIBRARY_MODE",
    "LOCK_HELD_ERRNOS",
    "close_locked",
    "is_windows",
    "fsync_directory",
    "isolate_process_tree",
    "kill_process_tree",
    "lock_exclusive",
    "release_lock",
    "release_lock_file",
    "replace_file",
]

#: The `errno` of the `OSError` `lock_exclusive` raises when another descriptor holds the lock.
#: POSIX `flock(LOCK_NB)` raises `BlockingIOError` (EWOULDBLOCK, EAGAIN; EACCES on some systems);
#: on Windows the `msvcrt` refusal is re-raised as `BlockingIOError(EWOULDBLOCK)`.
LOCK_HELD_ERRNOS: Final = (errno.EWOULDBLOCK, errno.EAGAIN, errno.EACCES)
#: Windows only: `os.replace` raises `PermissionError` while another process has the target (or
#: the source) open; it is retried this many times, `REPLACE_RETRY_S` apart, then raised.
REPLACE_ATTEMPTS: Final = 50
REPLACE_RETRY_S: Final = 0.02
#: The `ctypes.CDLL` mode that opens a shared library only if it is already loaded (the BLAS and
#: OpenMP thread probes, which find their libraries in `/proc/self/maps`): POSIX
#: `RTLD_NOLOAD | RTLD_LAZY`. Windows has no such mode, and no caller reaches it there.
if sys.platform == "win32":
    LOADED_LIBRARY_MODE: Final[int] = 0
else:
    LOADED_LIBRARY_MODE: Final[int] = os.RTLD_NOLOAD | os.RTLD_LAZY


def is_windows() -> bool:
    """Whether this interpreter runs on Windows (`sys.platform`, read at each call). A caller
    that refuses Windows tests this rather than `sys.platform` itself, so that the type checker
    does not take the rest of the caller as unreachable on the Windows leg."""
    return sys.platform == "win32"


# ---------------------------------------------------------------------------------- file locks


def lock_exclusive(fd: int) -> None:
    """Take an exclusive lock on the open descriptor `fd` without blocking.

    Raises `BlockingIOError` (its `errno` in `LOCK_HELD_ERRNOS`) when another open descriptor holds
    the lock, in this process or another; any other `OSError` is the system's. POSIX:
    `flock(fd, LOCK_EX | LOCK_NB)`, released by the kernel when the process dies. Windows:
    `msvcrt.locking(LK_NBLCK)` on byte 0, which a lock file need not contain, released by the
    system when the handle closes or the process dies."""
    if sys.platform == "win32":
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except PermissionError as error:  # EACCES: the byte is locked through another handle
            raise BlockingIOError(errno.EWOULDBLOCK, os.strerror(errno.EWOULDBLOCK)) from error
    else:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)


def release_lock(fd: int) -> None:
    """Release the lock `lock_exclusive` took on `fd`; the descriptor stays open."""
    if sys.platform == "win32":
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)


def close_locked(fd: int) -> None:
    """Close `fd`, releasing the lock `lock_exclusive` may have taken on it. POSIX: `os.close`,
    which drops the `flock`. Windows releases the byte first, as `msvcrt` asks (a lock left to the
    close is dropped when the system gets to it), ignoring the error when no lock was taken."""
    if sys.platform == "win32":
        try:
            release_lock(fd)
        except OSError:
            pass
    os.close(fd)


def release_lock_file(fd: int, path: Path) -> None:
    """Remove the lock file `path`, and release and close `fd`, the lock held on it.

    POSIX removes the file first, while the lock is held, so that a prober opening `path`
    afterwards finds no file. Windows cannot remove a file that is open: the lock is released and
    the handle closed first, and a prober that opened the file in between keeps it (its own
    `release_lock_file` removes it); the `PermissionError` that this case raises is ignored."""
    if sys.platform == "win32":
        release_lock(fd)
        os.close(fd)
        try:
            path.unlink(missing_ok=True)
        except PermissionError:
            pass
    else:
        try:
            path.unlink(missing_ok=True)
        finally:
            release_lock(fd)
            os.close(fd)


# ------------------------------------------------------------------------------- process trees


def isolate_process_tree() -> None:
    """Make the calling process the root of a tree that `kill_process_tree` (or, on Windows, the
    parent's `Process.kill()`) ends as a whole; called first in a new worker (ADR 0033 D2 L2).

    POSIX: `os.setpgid(0, 0)`, a new process group led by this process; its children join it.
    Windows: a new Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, this process assigned to
    it, and the only handle to it held here and not inherited. The children this process spawns
    join the job; when this process ends, however it ends (`Process.kill()` is
    `TerminateProcess`), its handle closes and the system ends every process still in the job.
    Raises `OSError` when the system refuses either step."""
    if sys.platform == "win32":
        _JOB_HANDLES.append(_kill_on_close_job())
    else:
        os.setpgid(0, 0)


def kill_process_tree(pid: int) -> bool:
    """Kill the tree `isolate_process_tree` rooted at the process `pid`; whether a kill was sent.

    POSIX: `os.killpg(pid, SIGKILL)`, the worker's group; `False` when there is no such group
    (`ProcessLookupError`, the worker died before `setpgid` or is gone) or it is not ours
    (`PermissionError`). Windows: always `False`; the caller's `Process.kill()` ends the worker,
    and with its job handle the rest of the tree."""
    if sys.platform == "win32":
        return False
    else:
        try:
            os.killpg(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            return False
        return True


#: Windows: the job handles `isolate_process_tree` holds for this process's lifetime.
_JOB_HANDLES: Final[list[int]] = []

if sys.platform == "win32":
    _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION: Final = 9
    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE: Final = 0x2000

    class _BasicLimits(ctypes.Structure):
        _fields_ = (
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        )

    class _IoCounters(ctypes.Structure):
        _fields_ = tuple(
            (name, ctypes.c_uint64)
            for name in ("Read", "Write", "Other", "ReadTransfer", "WriteTransfer", "OtherTransfer")
        )

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = (
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        )

    def _kill_on_close_job() -> int:
        """A new kill-on-close Job Object with the calling process in it; its handle."""
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        kernel32.CreateJobObjectW.argtypes = (wintypes.LPVOID, wintypes.LPCWSTR)
        kernel32.SetInformationJobObject.restype = wintypes.BOOL
        kernel32.SetInformationJobObject.argtypes = (
            wintypes.HANDLE,
            ctypes.c_int,
            wintypes.LPVOID,
            wintypes.DWORD,
        )
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel32.SetInformationJobObject(
            job, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            raise ctypes.WinError(ctypes.get_last_error())
        if not kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(job)


# ------------------------------------------------------------------------------ atomic replace


def replace_file(source: Path, target: Path) -> None:
    """`os.replace(source, target)`. On Windows a `PermissionError` (another process has either
    file open, without delete sharing) is retried `REPLACE_ATTEMPTS` times, `REPLACE_RETRY_S`
    apart, and then raised."""
    if sys.platform == "win32":
        for attempt in range(REPLACE_ATTEMPTS):
            try:
                os.replace(source, target)
                return
            except PermissionError:
                if attempt == REPLACE_ATTEMPTS - 1:
                    raise
                time.sleep(REPLACE_RETRY_S)
    else:
        os.replace(source, target)


def fsync_directory(directory: Path) -> None:
    """`fsync` the directory `directory`, so that a rename in it is durable. POSIX only: Windows
    cannot open a directory as a file; there a rename is as durable as the file system's own
    metadata journal makes it (a stated limitation, docs/X07a_DECISIONS.md)."""
    if sys.platform != "win32":
        handle = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(handle)
        finally:
            os.close(handle)
