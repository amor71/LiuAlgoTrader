import asyncio
from datetime import date

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.trading.alpaca import AlpacaTrader

alpaca_trader: AlpacaTrader


@pytest.fixture
def event_loop():
    global alpaca_trader
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create_db_connection())
    alpaca_trader = AlpacaTrader()
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_equity_trading_days():
    global alpaca_trader
    days = alpaca_trader.get_equity_trading_days(
        date(year=2023, month=1, day=1), date(year=2023, month=1, day=10)
    )
    num_trading_days = len(days)
    print(days, num_trading_days)

    assert (
        len(days) == 6
    ), f"expected 6 trading days and got {num_trading_days} "


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_crypto_trading_days():
    global alpaca_trader
    days = alpaca_trader.get_crypto_trading_days(
        date(year=2023, month=1, day=1), date(year=2023, month=1, day=10)
    )
    num_trading_days = len(days)
    print(days, num_trading_days)

    assert (
        len(days) == 10
    ), f"expected 10 trading days and got {num_trading_days} "


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_symbols():
    global alpaca_trader
    assets = await alpaca_trader.get_tradeable_symbols()
    print(assets)
    print(len(assets))


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_shortable_symbols():
    global alpaca_trader
    assets = await alpaca_trader.get_shortable_symbols()
    print(assets)
    print(len(assets))


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_is_fractionable():
    global alpaca_trader
    apa_fractionable = await alpaca_trader.is_fractionable("APA")
    print("APA:", apa_fractionable)
    if not apa_fractionable:
        print("APA is not fractionable")
    aapl_fractionable = await alpaca_trader.is_fractionable("AAPL")
    print("AAPL:", aapl_fractionable)
    if not aapl_fractionable:
        print("AAPL is fractionable ")
