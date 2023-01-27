import time
from datetime import date, datetime
from datetime import time as ttime

import pandas as pd
import pytest

from liualgotrader.common.types import TimeScale
from liualgotrader.data.alpaca import AlpacaData
from liualgotrader.trading.alpaca import AlpacaTrader


@pytest.mark.devtest
def test_alpaca_aapl_data_day():
    alpaca = AlpacaData()
    print(
        alpaca.get_symbol_data(
            "AAPL",
            datetime.combine(date(year=2021, month=2, day=1), ttime.min),
            datetime.combine(date(year=2021, month=2, day=2), ttime.max),
            scale=TimeScale.day,
        )
    )


@pytest.mark.devtest
def test_alpaca_aapl_data_min():
    alpaca = AlpacaData()
    print(
        alpaca.get_symbol_data(
            "AAPL",
            datetime.combine(date(year=2021, month=2, day=1), ttime.min),
            datetime.combine(date(year=2021, month=2, day=2), ttime.max),
        ).between_time("9:30", "16:00")
    )


@pytest.mark.asyncio
async def test_alpaca_get_symbols():
    AlpacaData()
    trader = AlpacaTrader()

    symbols = trader.get_symbols()
    print(f"{symbols}, number of symbols {len(symbols)}")

    assert len(symbols) > 1000, "too few tradable symbols {len(symbols)}"


@pytest.mark.asyncio
async def test_alpaca_get_market_snapshot():
    alpaca = AlpacaData()
    trader = AlpacaTrader()

    t0 = time.time()
    market_snapshots = await alpaca.get_market_snapshot(
        symbols=trader.get_symbols()
    )
    t1 = time.time()
    print(
        f"{len(market_snapshots)} tickers of market snapshots are retrieved from Alpaca in {t1-t0} seconds"
    )


@pytest.mark.devtest
def test_alpaca_multi_symbols_min():
    alpaca = AlpacaData()
    print(
        alpaca.get_symbols_data(
            ["AAPL", "IBM"],
            datetime.combine(date(year=2021, month=2, day=1), ttime.min),
            datetime.combine(date(year=2021, month=2, day=2), ttime.max),
        )
    )


@pytest.mark.devtest
def test_alpaca_multi_symbols_day():
    alpaca = AlpacaData()
    print(
        alpaca.get_symbols_data(
            ["AAPL", "IBM"],
            datetime.combine(date(year=2021, month=2, day=1), ttime.min),
            datetime.combine(date(year=2021, month=2, day=2), ttime.max),
            TimeScale.day,
        )
    )


@pytest.mark.devtest
def test_alpaca_multi_symbols_min_negative():
    try:
        AlpacaData().get_symbols_data(
            "AAPL",  # type:ignore
            datetime.combine(date(year=2021, month=2, day=1), ttime.min),
            datetime.combine(date(year=2021, month=2, day=2), ttime.max),
        )
    except AssertionError:
        return

    raise AssertionError("excepted an error")
