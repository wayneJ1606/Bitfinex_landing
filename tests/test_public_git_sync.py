from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from bitfinex_lending.public_git_sync import (
    SyncError,
    collect_public_files,
    push_with_retries,
    synchronize,
)


def _write(path: Path, content: str = "market,rate\nfUST,0.0002\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )


def _bare_remote(tmp_path: Path) -> Path:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    remote.mkdir()
    _git(remote, "init", "--bare", "--initial-branch=master")
    seed.mkdir()
    _git(seed, "init", "--initial-branch=master")
    _git(seed, "config", "user.name", "Test User")
    _git(seed, "config", "user.email", "test@example.invalid")
    _write(seed / "README.md", "seed\n")
    _git(seed, "add", "README.md")
    _git(seed, "commit", "-m", "seed")
    _git(seed, "remote", "add", "origin", str(remote))
    _git(seed, "push", "-u", "origin", "master")
    return remote


def test_collects_only_approved_public_subtrees(tmp_path: Path) -> None:
    approved = tmp_path / "data/local_public/raw/2026/08/16/fUST.csv"
    private = tmp_path / "data/account/funding_trades/2026/08/16.csv"
    _write(approved)
    _write(private, "offer_id\n1\n")

    assert collect_public_files(tmp_path) == (approved.resolve(),)


def test_rejects_private_field_names_in_public_csv(tmp_path: Path) -> None:
    path = tmp_path / "data/local_public/raw/2026/08/16/fUST.csv"
    _write(path, "offer_id,raw_payload\n1,secret\n")

    with pytest.raises(SyncError, match="forbidden public fields"):
        collect_public_files(tmp_path)


def test_push_retry_is_bounded() -> None:
    attempts = 0

    def fail_twice() -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise subprocess.CalledProcessError(1, ["git", "push"])

    assert push_with_retries(fail_twice, max_attempts=3) == 3


def test_synchronizes_to_local_remote_and_second_run_is_noop(tmp_path: Path) -> None:
    remote = _bare_remote(tmp_path)
    project = tmp_path / "project"
    public_file = project / "data/local_public/raw/2026/08/16/fUST.csv"
    _write(public_file)

    first = synchronize(project, branch="master", push=True, remote_url=str(remote))
    second = synchronize(project, branch="master", push=True, remote_url=str(remote))

    assert first.status == "success"
    assert first.file_count == 1
    assert second.status == "no_changes"
    shown = subprocess.run(
        [
            "git",
            f"--git-dir={remote}",
            "show",
            "master:data/local_public/raw/2026/08/16/fUST.csv",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "fUST" in shown.stdout
    tree = subprocess.run(
        ["git", f"--git-dir={remote}", "ls-tree", "-r", "--name-only", "master"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    assert "data/account/funding_trades/2026/08/16.csv" not in tree
