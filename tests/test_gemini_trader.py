import asyncio

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.trading.gemini import GeminiTrader

gemini_trader: GeminiTrader


@pytest.fixture
def event_loop():
    global gemini_trader
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create_db_connection())
    gemini_trader = GeminiTrader()
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_symbols():
    print("test_get_symbols")
    global gemini_trader
    assets = await gemini_trader.get_tradeable_symbols()
    print(assets)
    print(len(assets))
    await asyncio.sleep(1.0)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_shortable_symbols():
    print("test_get_shortable_symbols")
    global gemini_trader
    assets = await gemini_trader.get_shortable_symbols()
    print(assets)
    print(len(assets))
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_market_buy_order():
    print("test_market_buy_order")
    global gemini_trader
    if gemini_trader.base_url != "https://api.sandbox.gemini.com":
        raise AssertionError("Can only run test in sandbox")

    try:
        order = await gemini_trader.submit_order(
            symbol="btcusd",
            qty=0.1,
            side="buy",
            order_type="market",
        )
    except AssertionError:
        return True

    raise AssertionError("Expected exception")


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_limit_buy_order():
    print("test_limit_buy_order")
    global gemini_trader
    if gemini_trader.base_url != "https://api.sandbox.gemini.com":
        raise AssertionError("Can only run test in sandbox")

    order = await gemini_trader.submit_order(
        symbol="btcusd",
        qty=0.1,
        side="buy",
        order_type="limit",
        limit_price="500",
    )
    await asyncio.sleep(1.0)
    order_status = await gemini_trader.get_order(order.order_id)
    print(order_status)
    await asyncio.sleep(1.0)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_order_negative():
    print("test_order_negative")
    global gemini_trader
    if gemini_trader.base_url != "https://api.sandbox.gemini.com":
        raise AssertionError("Can only run test in sandbox")

    try:
        await gemini_trader.get_order("abccccasd")
    except Exception:
        await asyncio.sleep(1.0)
        return True
    raise AssertionError("test_order_negative() exe")


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_order_completed():
    print("test_order_completed")
    global gemini_trader
    if gemini_trader.base_url != "https://api.sandbox.gemini.com":
        raise AssertionError("Can only run test in sandbox")

    order = await gemini_trader.submit_order(
        symbol="btcusd",
        qty=0.1,
        side="buy",
        limit_price="20000",
        order_type="limit",
    )
    await asyncio.sleep(1.0)
    order_status = await gemini_trader.is_order_completed(order.order_id)
    print(order_status)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_buy_websocket1():
    print("test_order_completed")
    global gemini_trader
    if gemini_trader.base_url != "https://api.sandbox.gemini.com":
        raise AssertionError("Can only run test in sandbox")

    task_id = await gemini_trader.run()
    print("task_id", task_id, "created")
    await asyncio.sleep(1.0)

    try:
        order = await gemini_trader.submit_order(
            symbol="btcusd",
            qty=1,
            side="buy",
            order_type="limit",
            limit_price="100000",
        )
    except AssertionError as e:
        print(f"Assertion Error {e}")
        return True

    await asyncio.sleep(30.0)
    order_status = await gemini_trader.is_order_completed(order)
    print(order_status)

    await gemini_trader.close()
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_position():
    print("test_get_position")
    global gemini_trader
    if gemini_trader.base_url != "https://api.sandbox.gemini.com":
        raise AssertionError("Can only run test in sandbox")

    await asyncio.sleep(1.0)
    position = gemini_trader.get_position("BTC")
    print("BTC=", position)

    return True
