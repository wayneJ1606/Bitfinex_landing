from __future__ import annotations

import os
import sys
from typing import IO, Any


if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


def _ensure_lockable_byte(handle: IO[Any]) -> None:
    handle.seek(0, os.SEEK_END)
    if handle.tell() != 0:
        return
    marker = b"0" if "b" in getattr(handle, "mode", "") else "0"
    handle.write(marker)
    handle.flush()


def try_lock(handle: IO[Any]) -> bool:
    """Acquire a non-blocking exclusive lock for the open file handle."""
    try:
        _ensure_lockable_byte(handle)
        handle.seek(0)
        if sys.platform == "win32":
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def unlock(handle: IO[Any]) -> None:
    """Release a lock previously acquired with :func:`try_lock`."""
    try:
        handle.seek(0)
        if sys.platform == "win32":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
