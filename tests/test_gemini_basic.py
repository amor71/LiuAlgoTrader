from datetime import date

import pytest

from liualgotrader.common import config
from liualgotrader.common.types import TimeScale
from liualgotrader.data.gemini import GeminiData


@pytest.mark.devtest
def test_gemini_data_day() -> bool:
    gemini = GeminiData()
    print(
        gemini.get_symbol_data(
            "BTCUSD",
            date(year=2021, month=9, day=1),
            date(year=2021, month=9, day=2),
            scale=TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_gemini_data_min() -> bool:
    gemini = GeminiData()
    print(
        gemini.get_symbol_data(
            "BTCUSD",
            date(year=2021, month=9, day=1),
            date(year=2021, month=9, day=2),
            scale=TimeScale.minute,
        )
    )
    return True
