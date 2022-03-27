import time
from datetime import date

import pandas as pd
import pytest

from liualgotrader.common import config
from liualgotrader.common.types import (QueueMapper, TimeScale, WSConnectState,
                                        WSEventType)
from liualgotrader.data.alpaca import AlpacaData


@pytest.mark.devtest
def test_alpaca_aapl_data_day() -> bool:
    alpaca = AlpacaData()
    print(
        alpaca.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
            scale=TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_alpaca_aapl_data_min() -> bool:
    alpaca = AlpacaData()
    print(
        alpaca.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
        ).between_time("9:30", "16:00")
    )
    return True


@pytest.mark.devtest
def test_alpaca_get_symbols() -> bool:
    alpaca = AlpacaData()

    t0 = time.time()
    symbols = alpaca.get_symbols()
    t1 = time.time()
    print(
        f"{len(symbols)} symbols are retrieved from Alpaca in {t1-t0} seconds"
    )
    return True


@pytest.mark.devtest
def test_alpaca_get_market_snapshot() -> bool:
    alpaca = AlpacaData()

    t0 = time.time()
    market_snapshots = alpaca.get_market_snapshot()
    t1 = time.time()
    print(
        f"{len(market_snapshots)} tickers of market snapshots are retrieved from Alpaca in {t1-t0} seconds"
    )
    return True


@pytest.mark.devtest
def test_alpaca_multi_symbols_min() -> bool:
    alpaca = AlpacaData()
    print(
        alpaca.get_symbols_data(
            ["AAPL", "IBM"],
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
        )
    )
    return True


@pytest.mark.devtest
def test_alpaca_multi_symbols_day() -> bool:
    alpaca = AlpacaData()
    print(
        alpaca.get_symbols_data(
            ["AAPL", "IBM"],
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
            TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_alpaca_multi_symbols_min_negative() -> bool:
    try:
        AlpacaData().get_symbols_data(
            "AAPL",  # type:ignore
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
        )
    except AssertionError:
        return True

    raise AssertionError("excepted an error")
