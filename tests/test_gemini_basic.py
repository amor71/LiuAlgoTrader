from datetime import date, datetime, timedelta

import pytest

from liualgotrader.common import config
from liualgotrader.common.types import TimeScale
from liualgotrader.data.gemini import GeminiData


@pytest.mark.devtest
def test_gemini_data_day() -> bool:
    gemini = GeminiData()
    from_date = datetime.today().date() - timedelta(days=25)
    to_date = from_date + timedelta(days=1)
    print(
        gemini.get_symbol_data(
            "BTCUSD",
            from_date,
            to_date,
            scale=TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_gemini_data_min() -> bool:
    gemini = GeminiData()
    from_date = datetime.today().date() - timedelta(days=25)
    to_date = from_date + timedelta(days=1)
    print(
        gemini.get_symbol_data(
            "BTCUSD",
            from_date,
            to_date,
            scale=TimeScale.minute,
        )
    )
    return True
