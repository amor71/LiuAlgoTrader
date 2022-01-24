import time
from datetime import date

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from liualgotrader.common.types import DataConnectorType, TimeScale
from liualgotrader.data.data_factory import data_loader_factory


def test_alpaca_num_trading_day():
    print("test_alpaca_num_trading_days_positive")
    alpaca_dl = data_loader_factory(DataConnectorType.alpaca)
    if (
        alpaca_dl.num_trading_days(
            symbol="AAPL", start="2022-01-06", end="2022-01-07"
        )
        != 2
    ):
        raise AssertionError("expected 2")

    if (
        alpaca_dl.num_trading_days(
            symbol="aapl", start="2022-01-06", end="2022-01-07"
        )
        != 2
    ):
        raise AssertionError("expected 2")

    if (
        alpaca_dl.num_trading_days(
            symbol="AAPL", start="2022-01-01", end="2022-01-07"
        )
        != 5
    ):
        raise AssertionError("expected 5")

    if (
        alpaca_dl.num_trading_days(
            symbol="AAPL", start="2021-12-28", end="2022-01-07"
        )
        != 9
    ):
        raise AssertionError("expected 9")

    if (
        alpaca_dl.num_trading_days(
            symbol="AAPL", start="2021-07-01", end="2021-07-07"
        )
        != 4
    ):
        raise AssertionError("expected 4")

    if (
        alpaca_dl.num_trading_days(
            symbol="BTCUSD", start="2021-07-01", end="2021-07-07"
        )
        != 7
    ):
        raise AssertionError("BTCUSD - expected 7")

    if (
        alpaca_dl.num_trading_days(
            symbol="AAPL", start="2022-08-06", end="2022-01-07"
        )
        != 0
    ):
        raise AssertionError("expected 0")

    return True


def test_alpaca_concurrency_ranges_min():
    print("test_alpaca_concurrency_ranges_min")
    alpaca_dl = data_loader_factory(DataConnectorType.alpaca)

    t = time.time()
    if (
        len(
            alpaca_dl.data_concurrency_ranges(
                symbol="AAPL",
                start="2021-11-10",
                end="2022-01-07",
                scale=TimeScale.minute,
            )
        )
        != 5
    ):
        raise AssertionError("expected 5")
    print(time.time() - t)

    t = time.time()
    if (
        len(
            alpaca_dl.data_concurrency_ranges(
                symbol="AAPL",
                start="2022-01-01",
                end="2022-01-07",
                scale=TimeScale.minute,
            )
        )
        != 2
    ):
        raise AssertionError("expected 2")
    print(time.time() - t)

    return True


@settings(deadline=None, max_examples=100)
@given(
    start=st.dates(min_value=date(2018, 1, 1), max_value=date(2022, 1, 1)),
    end=st.dates(min_value=date(2018, 1, 1), max_value=date(2022, 1, 1)),
)
def test_hpy_alpaca_concurrency_ranges_min(start: date, end: date):
    alpaca_dl = data_loader_factory(DataConnectorType.alpaca)

    t = time.time()
    r = alpaca_dl.data_concurrency_ranges(
        symbol="AAPL", start=start, end=end, scale=TimeScale.minute
    )
    duration = time.time() - t

    print(f"duration={duration}, len={len(r)} -> {r}")
