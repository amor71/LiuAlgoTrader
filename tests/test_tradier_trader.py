import asyncio

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.trading.tradier import TradierTrader

tradier_trader: TradierTrader


@pytest.fixture
def event_loop():
    global tradier_trader
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    tradier_trader = TradierTrader()
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_symbols():
    global tradier_trader
    assets = await tradier_trader.get_tradeable_symbols()
    print(assets)
    print(len(assets))
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_shortable_symbols():
    global tradier_trader
    assets = await tradier_trader.get_shortable_symbols()
    print(assets)
    print(len(assets))
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_is_fractionable():
    global tradier_trader
    apa_fractionable = await tradier_trader.is_fractionable("APA")
    print("APA:", apa_fractionable)

    if not apa_fractionable:
        print("APA is not fractionable")
    aapl_fractionable = await tradier_trader.is_fractionable("AAPL")
    print("AAPL:", aapl_fractionable)
    if not aapl_fractionable:
        print("AAPL is fractionable ")

    return True
