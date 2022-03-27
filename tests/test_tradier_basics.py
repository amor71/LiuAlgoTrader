from datetime import date, timedelta

import pytest

from liualgotrader.common.types import TimeScale
from liualgotrader.data.tradier import TradierData


@pytest.mark.devtest
def test_tradier_aapl_data_day() -> bool:
    tradier = TradierData()
    print(
        tradier.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
            scale=TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_tradier_aapl_data_min() -> bool:
    tradier = TradierData()
    print(
        tradier.get_symbol_data(
            "AAPL",
            start=date.today() - timedelta(days=10),
            end=date.today() - timedelta(days=1),
            scale=TimeScale.minute,
        )
    )
    return True
