from pathlib import Path


SCRIPT = Path("scripts/install-public-github-sync.ps1")


def test_public_sync_schedule_is_weekly_preview_first_and_hidden() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    for token in (
        "BitfinexPublicGitHubSync",
        "-Weekly",
        "-DaysOfWeek Monday",
        '10:00',
        "StartWhenAvailable",
        "IgnoreNew",
        "pythonw.exe",
        "--push",
        "registration=not_requested",
        "-Enable",
    ):
        assert token in text


def test_public_sync_script_contains_no_private_or_broad_git_staging() -> None:
    text = SCRIPT.read_text(encoding="utf-8").lower()
    for forbidden in (
        "bitfinex_readonly_api_key",
        "bitfinex_readonly_api_secret",
        "data/account",
        "git add .",
        "github_token",
    ):
        assert forbidden not in text
