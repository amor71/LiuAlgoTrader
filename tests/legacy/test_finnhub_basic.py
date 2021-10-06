from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from liualgotrader.common import config
from liualgotrader.common.types import (QueueMapper, TimeScale, WSConnectState,
                                        WSEventType)
from liualgotrader.data.finnhub import FinnhubData


@pytest.mark.devtest
def test_create_finnhub() -> bool:
    finnhub = FinnhubData()
    print(finnhub.stock_exchanges)
    return True


@pytest.mark.devtest
def test_finnhub_us_symbols() -> bool:
    finnhub = FinnhubData()
    print(finnhub.get_symbols())
    return True


@pytest.mark.devtest
def test_finnhub_aapl_data_day() -> bool:
    finnhub = FinnhubData()
    print(
        finnhub.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
            scale=TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_finnhub_aapl_data_min() -> bool:
    finnhub = FinnhubData()
    print(
        finnhub.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
        ).between_time("9:30", "16:00")
    )
    return True
