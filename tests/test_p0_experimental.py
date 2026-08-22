from __future__ import annotations

from decimal import Decimal

import pytest

from bitfinex_lending.p0_experimental import (
    ExperimentalProductError,
    NativeMarketEstimate,
    build_native_scenarios,
)


def estimate(asset: str, market: str, conversion: str) -> NativeMarketEstimate:
    return NativeMarketEstimate(
        asset=asset,
        market=market,
        model_name="baseline_previous",
        predicted_daily_rate=Decimal("0.001"),
        prediction_as_of="2026-08-22T14:00:00+00:00",
        rmse=Decimal("0.00001"),
        native_to_usdt=Decimal(conversion),
        conversion_as_of="2026-08-22T14:47:00+00:00",
        conversion_note="test conversion",
    )


def test_native_scenario_keeps_interest_in_asset_and_converts_only_for_display() -> None:
    rows = build_native_scenarios(
        (estimate("BTC", "fBTC", "50000"),),
        capitals_usdt=(Decimal("1000"),),
        periods=(2,),
    )

    row = rows[0]
    assert row.asset == "BTC"
    assert row.principal_native == Decimal("0.02")
    assert row.net_interest_native == Decimal("0.000034000")
    assert row.ending_native == Decimal("0.020034000")
    assert row.net_interest_usdt == Decimal("1.700000000")
    assert row.assumption == "fully_matched_for_entire_period"


def test_usd_may_use_disclosed_one_to_one_amount_conversion() -> None:
    row = build_native_scenarios(
        (estimate("USD", "fUSD", "1"),),
        capitals_usdt=(Decimal("1000"),),
        periods=(5,),
    )[0]

    assert row.principal_native == Decimal("1000")
    assert row.net_interest_native == Decimal("4.25000")
    assert row.net_interest_usdt == Decimal("4.25000")


def test_fust_market_behavior_is_rejected_from_experimental_proxy_scenarios() -> None:
    with pytest.raises(ExperimentalProductError, match="fUST"):
        build_native_scenarios(
            (estimate("USDT", "fUST", "1"),),
            capitals_usdt=(Decimal("1000"),),
            periods=(2,),
        )


@pytest.mark.parametrize("period", [1, 3, 7, 31])
def test_only_approved_periods_are_accepted(period: int) -> None:
    with pytest.raises(ExperimentalProductError, match="period"):
        build_native_scenarios(
            (estimate("USD", "fUSD", "1"),),
            capitals_usdt=(Decimal("1000"),),
            periods=(period,),
        )
