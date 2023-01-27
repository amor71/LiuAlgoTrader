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
            symbol="BTC/USD", start="2021-07-01", end="2021-07-07"
        )
        != 7
    ):
        raise AssertionError("BTC/USD - expected 7")

    if (
        alpaca_dl.num_trading_days(
            symbol="AAPL", start="2022-08-06", end="2022-01-07"
        )
        != 0
    ):
        raise AssertionError("expected 0")


def test_alpaca_concurrency_ranges_min():
    print("test_alpaca_concurrency_ranges_min")
    alpaca_dl = data_loader_factory(DataConnectorType.alpaca)

    t = _extracted_from_test_alpaca_concurrency_ranges_min_5(
        alpaca_dl, "2021-11-10", 5, "expected 5"
    )
    t = _extracted_from_test_alpaca_concurrency_ranges_min_5(
        alpaca_dl, "2022-01-01", 2, "expected 2"
    )


# TODO Rename this here and in `test_alpaca_concurrency_ranges_min`
def _extracted_from_test_alpaca_concurrency_ranges_min_5(
    alpaca_dl, start, arg2, arg3
):
    result = time.time()
    if (
        len(
            alpaca_dl.data_concurrency_ranges(
                symbol="AAPL",
                start=start,
                end="2022-01-07",
                scale=TimeScale.minute,
            )
        )
        != arg2
    ):
        raise AssertionError(arg3)
    print(time.time() - result)

    return result


@settings(deadline=None, max_examples=100)
@given(
    start=st.dates(min_value=date(2018, 1, 1), max_value=date(2022, 1, 1)),
    end=st.dates(min_value=date(2018, 1, 1), max_value=date(2022, 1, 1)),
)
def test_hpy_alpaca_concurrency_ranges_min(start: date, end: date):
    alpaca_dl = data_loader_factory(DataConnectorType.alpaca)

    t = time.time()
    r = alpaca_dl.data_concurrency_ranges(
        symbol="AAPL",
        start=start,  # type:ignore
        end=end,  # type:ignore
        scale=TimeScale.minute,  # type:ignore
    )
    duration = time.time() - t

    print(f"duration={duration}, len={len(r)} -> {r}")
