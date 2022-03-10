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
    print("test_get_symbols")
    assets = await tradier_trader.get_tradeable_symbols()
    print(assets)
    print(len(assets))
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_shortable_symbols():
    print("test_get_shortable_symbols")
    assets = await tradier_trader.get_shortable_symbols()
    print(assets)
    print(len(assets))
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_is_aapl_shortable():
    print("test_is_aapl_shortable")
    shortable = await tradier_trader.is_shortable("AAPL")

    if not shortable:
        raise AssertionError("expected AAPL to be shortable")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_is_fractionable():
    print("test_is_fractionable")
    apa_fractionable = await tradier_trader.is_fractionable("APA")
    if not apa_fractionable:
        print("APA is not fractionable")
    aapl_fractionable = await tradier_trader.is_fractionable("AAPL")
    if not aapl_fractionable:
        print("AAPL is fractionable ")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_market_schedule():
    print("test_get_market_schedule")
    open, close = await tradier_trader.get_market_schedule()
    print(f"market open {open} close {close}")

    return True
