import os

os.environ["DATA_CONNECTOR"] = "alpaca"
import asyncio
from datetime import date

import pandas as pd
import pytest

from liualgotrader.analytics import analysis
from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import DataConnectorType

# @pytest.mark.devtest
# def test_spyreturns() -> bool:
#    td = analysis.compare_to_symbol_returns(
#        "0664dc2c-f126-4c7f-a069-c5dc246e2df4", "SPY"
#    )
#    print(td)
#    return True


@pytest.fixture
def event_loop():
    global alpaca_trader
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.devtest
def test_returns() -> bool:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    td = analysis.calc_batch_returns("0664dc2c-f126-4c7f-a069-c5dc246e2df4")
    print(td)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_load_trades_by_portfolio():
    trades = analysis.load_trades_by_portfolio(
        "71f0eaa7-281a-40ad-b120-d2f74eb0b05d"
    )

    print(trades)

    return True
