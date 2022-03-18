import asyncio
import time
from datetime import date, timedelta

import pytest

from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import DataConnectorType, Order, TimeScale
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
        print("AAPL is not fractionable ")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_market_schedule():
    print("test_get_market_schedule")
    start, end = tradier_trader.get_market_schedule()
    print(f"market open {start} close {end}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_is_market_open_today():
    print("test_is_market_open_today")
    is_open = tradier_trader.is_market_open_today()
    print(f"Market open today {is_open}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_time_market_close():
    print("test_get_time_market_close")
    when_close = tradier_trader.get_time_market_close()
    print(f"Market close today {when_close}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_trading_days():
    print("test_get_trading_days")
    td = tradier_trader.get_trading_days(
        start_date=date.today(), end_date=date.today()
    )
    print(f"trading days {td}")

    print("test_get_trading_days")
    td = tradier_trader.get_trading_days(
        start_date=date.today() - timedelta(days=5), end_date=date.today()
    )
    print(f"trading days {td}")

    print("test_get_trading_days")
    td = tradier_trader.get_trading_days(
        start_date=date.today() - timedelta(days=65), end_date=date.today()
    )
    print(f"trading days {td}")
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_aapl_order_market_long():
    print("test_aapl_order_market_long")

    open_position = tradier_trader.get_position(symbol="AAPL")
    print(f"Open position in Apple is {open_position}")
    order = await tradier_trader.submit_order(
        symbol="AAPL", qty=10, side="buy", order_type="market"
    )
    print("submitted order:", order)

    for _ in range(5):
        order = await tradier_trader.get_order(order_id=order.order_id)
        print("pulled order:", order)

        if order.remaining_amount == 0.0:
            break
        time.sleep(0.5)

    position = tradier_trader.get_position(symbol="AAPL")

    print(f"New position in Apple is {position}")

    order = await tradier_trader.submit_order(
        symbol="AAPL", qty=10, side="sell", order_type="market"
    )
    print("submitted order:", order)

    for _ in range(5):
        order = await tradier_trader.get_order(order_id=order.order_id)
        print("pulled order:", order)

        if order.remaining_amount == 0.0:
            break
        time.sleep(0.5)

    position = tradier_trader.get_position(symbol="AAPL")
    print(f"New position in Apple is {position}")

    if position != open_position:
        raise AssertionError(
            "position after buy & sell was supposed to be same as open position"
        )
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_aapl_order_limit_long():
    print("test_aapl_order_limit_long")

    open_position = tradier_trader.get_position(symbol="AAPL")
    print(f"Open position in Apple is {open_position}")

    dl = DataLoader(connector=DataConnectorType.tradier)

    last_price = dl["AAPL"].close[-1]

    print("last_price=", last_price)
    print(dl["AAPL"].close)
    order = await tradier_trader.submit_order(
        symbol="AAPL",
        qty=10,
        side="buy",
        order_type="limit",
        limit_price=last_price,
    )
    print("submitted order:", order)
    success = False
    for _ in range(5):
        order = await tradier_trader.get_order(order_id=order.order_id)
        print("pulled order:", order)

        if order.remaining_amount == 0.0:
            success = True
            break
        time.sleep(0.5)

    position = tradier_trader.get_position(symbol="AAPL")

    if success:
        time.sleep(10.0)
        print(f"New position in Apple is {position}")

        last_price = dl["AAPL"].close[-1]
        print("last_price=", last_price)
        order = await tradier_trader.submit_order(
            symbol="AAPL",
            qty=10,
            side="sell",
            order_type="limit",
            limit_price=last_price,
        )
        print("submitted order:", order)

        for _ in range(5):
            order = await tradier_trader.get_order(order_id=order.order_id)
            print("pulled order:", order)

            is_filled, _, _, _ = await tradier_trader.is_order_completed(
                order_id=order.order_id
            )
            print("is_filled", is_filled)
            if is_filled == Order.EventType.fill:
                break
            time.sleep(0.5)

        position = tradier_trader.get_position(symbol="AAPL")
        print(f"New position in Apple is {position}")

        if position != open_position:
            raise AssertionError(
                "position after buy & sell was supposed to be same as open position"
            )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_tsla_order_market_short():
    print("test_tsla_order_market_short")

    open_position = tradier_trader.get_position(symbol="TSLA")
    print(f"Open position in Tesla is {open_position}")

    order = await tradier_trader.submit_order(
        symbol="TSLA", qty=10, side="sell_short", order_type="market"
    )
    print("submitted order:", order)

    sold = False
    for _ in range(5):
        order = await tradier_trader.get_order(order_id=order.order_id)
        print("pulled order:", order)

        is_filled, _, _, _ = await tradier_trader.is_order_completed(
            order_id=order.order_id
        )

        print("is_filled", is_filled)
        if is_filled == Order.EventType.fill:
            sold = True
            break

        time.sleep(0.5)

    if sold:
        position = tradier_trader.get_position(symbol="TSLA")
        print(f"New position in is {position}")

        order = await tradier_trader.submit_order(
            symbol="TSLA", qty=10, side="buy_to_cover", order_type="market"
        )
        print("submitted order:", order)

        for _ in range(5):
            order = await tradier_trader.get_order(order_id=order.order_id)
            print("pulled order:", order)

            is_filled, _, _, _ = await tradier_trader.is_order_completed(
                order_id=order.order_id
            )
            print("is_filled", is_filled)
            if is_filled == Order.EventType.fill:
                break

            time.sleep(0.5)

        position = tradier_trader.get_position(symbol="TSLA")
        print(f"New position is {position}")

        if position != open_position:
            raise AssertionError(
                "position after buy & sell to be same as open position"
            )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_tsla_cancel_order():
    print("test_tsla_cancel_order")

    order = await tradier_trader.submit_order(
        symbol="AAPL", qty=10, side="buy", order_type="market"
    )
    print("submitted order:", order)

    try:
        cancelled = await tradier_trader.cancel_order(order)
        print("cancelled=", cancelled)
    except Exception as e:
        print(f"[EXCEPTION] {e}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_aapl_order_limit_long_websocket():
    print("test_aapl_order_limit_long_websocket")

    task_id = await tradier_trader.run()
    print("task_id", task_id, "created")
    await asyncio.sleep(1.0)

    open_position = tradier_trader.get_position(symbol="AAPL")
    print(f"Open position in Apple is {open_position}")

    dl = DataLoader(connector=DataConnectorType.tradier)
    last_price = dl["AAPL"].close[-1]

    print("last_price=", last_price)
    print(dl["AAPL"].close)
    order = await tradier_trader.submit_order(
        symbol="AAPL",
        qty=10,
        side="buy",
        order_type="limit",
        limit_price=last_price,
    )
    print("submitted order:", order)

    await asyncio.sleep(60.0)
    await tradier_trader.close()

    order = await tradier_trader.get_order(order_id=order.order_id)
    print("pulled order:", order)

    return True
