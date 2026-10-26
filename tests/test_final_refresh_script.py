from pathlib import Path


SCRIPT = Path("scripts/run-final-refresh.ps1")


def test_final_refresh_rebuilds_local_model_before_strategy_dashboard() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    model_command = "bitfinex_lending.modeling"
    strategy_command = "-m bitfinex_lending.p0_strategy_pipeline"

    assert "data/local_public/raw" in text
    assert "data/modeling" in text
    assert model_command in text
    assert strategy_command in text
    assert text.index(model_command) < text.index(strategy_command)
    assert text.count("$LASTEXITCODE -ne 0") == 2
