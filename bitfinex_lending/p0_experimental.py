"""Safe experimental scenarios built only from each asset's native market model."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .p0_economics import capital_levels, gross_interest, net_interest


APPROVED_PERIODS = (2, 5, 10, 30)
NATIVE_MARKETS = {"fUSD": "USD", "fBTC": "BTC", "fETH": "ETH"}


class ExperimentalProductError(ValueError):
    """Raised when a scenario would make an unsupported market inference."""


@dataclass(frozen=True)
class NativeMarketEstimate:
    asset: str
    market: str
    model_name: str
    predicted_daily_rate: Decimal
    prediction_as_of: str
    rmse: Decimal
    native_to_usdt: Decimal
    conversion_as_of: str
    conversion_note: str


@dataclass(frozen=True)
class NativeScenario:
    asset: str
    market: str
    model_name: str
    prediction_as_of: str
    capital_usdt: Decimal
    principal_native: Decimal
    daily_rate: Decimal
    period_days: int
    gross_interest_native: Decimal
    fee_native: Decimal
    net_interest_native: Decimal
    ending_native: Decimal
    native_to_usdt: Decimal
    net_interest_usdt: Decimal
    ending_usdt: Decimal
    conversion_as_of: str
    conversion_note: str
    assumption: str = "fully_matched_for_entire_period"


def _validate_estimate(estimate: NativeMarketEstimate) -> None:
    expected_asset = NATIVE_MARKETS.get(estimate.market)
    if expected_asset is None:
        raise ExperimentalProductError(
            f"{estimate.market} is excluded: fUST market behavior cannot use an fUSD proxy"
        )
    if estimate.asset != expected_asset:
        raise ExperimentalProductError(
            f"{estimate.market} must remain denominated in {expected_asset}"
        )
    if estimate.native_to_usdt <= 0:
        raise ExperimentalProductError("native_to_usdt must be greater than zero")


def build_native_scenarios(
    estimates: tuple[NativeMarketEstimate, ...],
    *,
    capitals_usdt: tuple[Decimal, ...] | None = None,
    periods: tuple[int, ...] = APPROVED_PERIODS,
) -> tuple[NativeScenario, ...]:
    """Calculate conditional returns without estimating fill or waiting behavior."""
    capitals = capitals_usdt or capital_levels()
    if any(capital not in capital_levels() for capital in capitals):
        raise ExperimentalProductError("capital must use the approved 1000 USDT grid")
    if any(period not in APPROVED_PERIODS for period in periods):
        raise ExperimentalProductError("period must be one of 2, 5, 10, or 30 days")

    rows: list[NativeScenario] = []
    for estimate in estimates:
        _validate_estimate(estimate)
        for capital in capitals:
            principal = capital / estimate.native_to_usdt
            for period in periods:
                seconds = period * 86400
                gross = gross_interest(principal, estimate.predicted_daily_rate, seconds)
                net = net_interest(principal, estimate.predicted_daily_rate, seconds)
                rows.append(
                    NativeScenario(
                        asset=estimate.asset,
                        market=estimate.market,
                        model_name=estimate.model_name,
                        prediction_as_of=estimate.prediction_as_of,
                        capital_usdt=capital,
                        principal_native=principal,
                        daily_rate=estimate.predicted_daily_rate,
                        period_days=period,
                        gross_interest_native=gross,
                        fee_native=gross - net,
                        net_interest_native=net,
                        ending_native=principal + net,
                        native_to_usdt=estimate.native_to_usdt,
                        net_interest_usdt=net * estimate.native_to_usdt,
                        ending_usdt=(principal + net) * estimate.native_to_usdt,
                        conversion_as_of=estimate.conversion_as_of,
                        conversion_note=estimate.conversion_note,
                    )
                )
    return tuple(rows)
