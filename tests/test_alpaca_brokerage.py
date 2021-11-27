import asyncio

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.trading.alpaca import AlpacaTrader

alpaca_trader: AlpacaTrader

account_id: str = "f6c9596e-e7ce-4ecc-8ed8-fe6c9720e96a"


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
async def test_sell_apple():
    global alpaca_trader
    global account_id

    try:
        order = await alpaca_trader.submit_order(
            symbol="AAPL",
            qty=2.0,
            side="sell",
            order_type="market",
            on_behalf_of=account_id,
        )
    except AssertionError as e:
        print(f"AssertionError with {e}")
    else:
        print(order)

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_buy_apple():
    global alpaca_trader
    global account_id
    try:
        order = await alpaca_trader.submit_order(
            symbol="AAPL",
            qty=2.0,
            side="buy",
            order_type="market",
            on_behalf_of=account_id,
        )
        print(order)
    except Exception as e:
        print(f"EXCEPTION: {e}")

    return True
