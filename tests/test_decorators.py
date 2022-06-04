import asyncio
from datetime import date

import pandas as pd
import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.trading.trader_factory import trader_factory


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


async def reconnect_trader():
    trader = trader_factory()
    return await trader.reconnect()


@timeit
async def get_trading_days(trader, start_date):
    return trader.get_trading_days(start_date)


@pytest.mark.devtest
@pytest.mark.asyncio
async def test_trader_calendar() -> bool:
    trader = trader_factory()

    td = await get_trading_days(
        trader=trader, start_date=date(year=2021, month=1, day=1)
    )
    print(td)
    return True
