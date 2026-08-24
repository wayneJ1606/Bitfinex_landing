from pathlib import Path


def test_private_and_runtime_paths_are_ignored() -> None:
    text = Path(".gitignore").read_text(encoding="utf-8")
    for rule in (
        "data/account/",
        "data/archive/",
        "data/metadata/account_collector_status.json",
        "data/metadata/private_collection_status.json",
        "data/metadata/collector_runs/**/private.csv",
        "data/metadata/public_git_sync_status.json",
        "data/local_public/**/*.tmp",
        "data/local_public/**/*.lock",
    ):
        assert rule in text


def test_env_example_names_readonly_variables_without_values() -> None:
    lines = Path(".env.example").read_text(encoding="utf-8").splitlines()
    assert lines == [
        "BITFINEX_READONLY_API_KEY=",
        "BITFINEX_READONLY_API_SECRET=",
    ]
