from __future__ import annotations

import subprocess
import sys


def test_collectors_import_without_msvcrt_on_linux() -> None:
    child_code = """
import builtins
import sys
import types

real_import = builtins.__import__

def guarded_import(name, *args, **kwargs):
    if name == "msvcrt":
        raise ModuleNotFoundError("msvcrt is unavailable on Linux")
    return real_import(name, *args, **kwargs)

fake_fcntl = types.ModuleType("fcntl")
fake_fcntl.LOCK_EX = 2
fake_fcntl.LOCK_NB = 4
fake_fcntl.LOCK_UN = 8
fake_fcntl.flock = lambda *args: None
sys.modules["fcntl"] = fake_fcntl
sys.platform = "linux"
builtins.__import__ = guarded_import

import bitfinex_lending.local_stable_collector
import bitfinex_lending.private_account_collector
"""

    completed = subprocess.run(
        [sys.executable, "-c", child_code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
