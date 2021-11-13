import asyncio
from datetime import date

import pandas as pd
import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.trading.trader_factory import trader_factory


@pytest.mark.devtest
def test_trader_calendar() -> bool:
    trader = trader_factory()

    td = trader.get_trading_days(start_date=date(year=2021, month=1, day=1))
    print(td)
    return True
