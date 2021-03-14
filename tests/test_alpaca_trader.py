import asyncio

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.trading.alpaca import AlpacaTrader

alpaca_trader: AlpacaTrader


@pytest.fixture
def event_loop():
    global alpaca_trader
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    alpaca_trader = AlpacaTrader()
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_symbols():
    global alpaca_trader
    assets = await alpaca_trader.get_tradeable_symbols()
    print(assets)
    print(len(assets))
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_shortable_symbols():
    global alpaca_trader
    assets = await alpaca_trader.get_shortable_symbols()
    print(assets)
    print(len(assets))
    return True
