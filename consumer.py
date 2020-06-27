import asyncio
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from multiprocessing import Queue
from typing import Dict, List

import alpaca_trade_api as tradeapi
import pandas as pd
import pygit2
from alpaca_trade_api.entity import Order
# from alpaca_trade_api.stream2 import StreamConn
from google.cloud import error_reporting
from pandas import DataFrame as df
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from common import config, market_data, trading_data
from common.database import create_db_connection
from common.tlog import tlog
from models.new_trades import NewTrade
from strategies.base import Strategy
from strategies.momentum_long import MomentumLong

error_logger = error_reporting.Client()


async def end_time(reason: str):
    for s in trading_data.strategies:
        tlog(f"updating end time for strategy {s.name}")
        await s.algo_run.update_end_time(
            pool=config.db_conn_pool, end_reason=reason
        )


async def teardown_task(tz: DstTzInfo, task: asyncio.Task) -> None:
    tlog(f"consumer-teardown_task() - starting ")
    to_market_close: timedelta
    try:
        dt = datetime.today().astimezone(tz)
        to_market_close = (
            config.market_close - dt
            if config.market_close > dt
            else timedelta(hours=24) + (config.market_close - dt)
        )
        tlog(
            f"consumer-teardown_task() - waiting for market close: {to_market_close}"
        )
    except Exception as e:
        tlog(
            f"consumer-teardown_task() - exception of type {type(e).__name__} with args {e.args}"
        )
        return

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 5)

        tlog("consumer-teardown_task() starting")
        await end_time("market close")

        tlog("consumer-teardown_task(): requesting tasks to cancel")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            tlog("consumer-teardown_task(): tasks are cancelled now")

    except asyncio.CancelledError:
        tlog("consumer-teardown_task() cancelled during sleep")
    except KeyboardInterrupt:
        tlog("consumer-teardown_task() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"consumer-teardown_task() - exception of type {type(e).__name__} with args {e.args}"
        )
        return
        # asyncio.get_running_loop().stop()
    finally:
        tlog("consumer-teardown_task() task done.")


async def liquidate(
    symbol: str, symbol_position: int, trading_api: tradeapi,
) -> None:

    if symbol_position:
        tlog(
            f"Trading over, trying to liquidating remaining position {symbol_position} in {symbol}"
        )
        try:
            trading_data.sell_indicators[symbol] = {"liquidation": 1}
            if symbol_position < 0:
                o = trading_api.submit_order(
                    symbol=symbol,
                    qty=str(-symbol_position),
                    side="buy",
                    type="market",
                    time_in_force="day",
                )
                op = "buy_short"
            else:

                o = trading_api.submit_order(
                    symbol=symbol,
                    qty=str(symbol_position),
                    side="sell",
                    type="market",
                    time_in_force="day",
                )
                op = "sell"

            trading_data.open_orders[symbol] = (o, op)
            trading_data.open_order_strategy[
                symbol
            ] = trading_data.last_used_strategy[symbol]

        except Exception as e:
            error_logger.report_exception()
            tlog(f"failed to liquidate {symbol} w exception {e}")


async def should_cancel_order(order: Order, market_clock: datetime) -> bool:
    # Make sure the order's not too old
    submitted_at = order.submitted_at.astimezone(timezone("America/New_York"))
    order_lifetime = market_clock - submitted_at
    if market_clock > submitted_at and order_lifetime.seconds // 60 >= 1:
        return True

    return False


async def save(
    symbol: str,
    new_qty: int,
    last_op: str,
    price: float,
    indicators: Dict,
    now: str,
) -> None:
    db_trade = NewTrade(
        algo_run_id=trading_data.open_order_strategy[symbol].algo_run.run_id,
        symbol=symbol,
        qty=new_qty,
        operation=last_op,
        price=price,
        indicators=indicators,
    )

    await db_trade.save(
        config.db_conn_pool,
        str(now),
        trading_data.stop_prices[symbol],
        trading_data.target_prices[symbol],
    )


async def get_order(api: tradeapi, order_id: str) -> Order:
    return api.get_order(order_id)


async def update_partially_filled_order(
    strategy: Strategy, order: Order
) -> None:
    qty = int(order.filled_qty)
    new_qty = qty - abs(trading_data.partial_fills.get(order.symbol, 0))
    if order.side == "sell":
        qty = qty * -1

    trading_data.positions[order.symbol] = trading_data.positions.get(
        order.symbol, 0
    ) - trading_data.partial_fills.get(order.symbol, 0)
    trading_data.partial_fills[order.symbol] = qty
    trading_data.positions[order.symbol] += qty
    trading_data.open_orders[order.symbol] = (
        order,
        trading_data.open_orders.get(order.symbol)[1],
    )

    await save(
        order.symbol,
        new_qty,
        trading_data.open_orders.get(order.symbol)[1],
        float(order.filled_avg_price),
        trading_data.buy_indicators[order.symbol]
        if order.side == "buy"
        else trading_data.sell_indicators[order.symbol],
        order.updated_at,
    )

    if order.side == "buy":
        await strategy.buy_callback(
            order.symbol, float(order.filled_avg_price), new_qty
        )
    else:
        await strategy.sell_callback(
            order.symbol, float(order.filled_avg_price), new_qty
        )


async def update_filled_order(strategy: Strategy, order: Order) -> None:
    qty = int(order.filled_qty)
    new_qty = qty - abs(trading_data.partial_fills.get(order.symbol, 0))
    if order.side == "sell":
        qty = qty * -1

    trading_data.positions[order.symbol] = trading_data.positions.get(
        order.symbol, 0
    ) - trading_data.partial_fills.get(order.symbol, 0)
    trading_data.partial_fills[order.symbol] = 0
    trading_data.positions[order.symbol] += qty

    indicators = (
        trading_data.buy_indicators[order.symbol]
        if order.side == "buy"
        else trading_data.sell_indicators[order.symbol]
    )
    await save(
        order.symbol,
        new_qty,
        trading_data.open_orders.get(order.symbol)[1],
        float(order.filled_avg_price),
        indicators if indicators else "",
        order.filled_at,
    )

    if order.side == "buy":
        trading_data.buy_indicators[order.symbol] = None
    else:
        trading_data.sell_indicators[order.symbol] = None

    if order.side == "buy":
        await strategy.buy_callback(
            order.symbol, float(order.filled_avg_price), new_qty
        )
    else:
        await strategy.sell_callback(
            order.symbol, float(order.filled_avg_price), new_qty
        )

    trading_data.open_orders.pop(order.symbol, None)
    trading_data.open_order_strategy.pop(order.symbol, None)


async def handle_trade_update(data: Dict) -> bool:
    symbol = data["symbol"]
    if trading_data.open_orders.get(symbol) is None:
        return False

    last_order = trading_data.open_orders.get(symbol)[0]
    if last_order is not None:
        event = data["event"]
        tlog(f"trade update for {symbol} data={data} with event {event}")

        if event == "partial_fill":
            await update_partially_filled_order(
                trading_data.open_order_strategy[symbol], Order(data["order"])
            )
        elif event == "fill":
            await update_filled_order(
                trading_data.open_order_strategy[symbol], Order(data["order"])
            )
        elif event in ("canceled", "rejected"):
            trading_data.partial_fills.pop(symbol, None)
            trading_data.open_orders.pop(symbol, None)
            trading_data.open_order_strategy.pop(symbol, None)

        return True
    else:
        tlog(f"{data['event']} trade update for {symbol} WITHOUT ORDER")

    return False


async def handle_data_queue_msg(data: Dict, trading_api: tradeapi) -> bool:
    symbol = data["symbol"]
    # print(f"got [{symbol}] to handle_queue_msg")

    # First, aggregate 1s bars for up-to-date MACD calculations
    original_ts = ts = pd.Timestamp(
        data["start"], tz="America/New_York", unit="ms"
    )
    ts = ts.replace(
        second=0, microsecond=0
    )  # timedelta(seconds=ts.second, microseconds=ts.microsecond)

    if symbol not in market_data.minute_history:
        _df = trading_api.polygon.historic_agg_v2(
            symbol,
            1,
            "minute",
            _from=str(date.today() - timedelta(days=10)),
            to=str(date.today() + timedelta(days=1)),
        ).df
        _df["vwap"] = 0.0
        _df["average"] = 0.0
        market_data.minute_history[symbol] = _df
    try:
        current = market_data.minute_history[symbol].loc[ts]
    except KeyError:
        current = None

    first_blood = False
    if current is None:
        new_data = [
            data["open"],
            data["high"],
            data["low"],
            data["close"],
            data["volume"],
            data["vwap"],
            data["average"],
        ]
        first_blood = True
    else:
        new_data = [
            current.open,
            max(data["high"], current.high),
            min(data["low"], current.low),
            data["close"],
            current.volume + data["volume"],
            data["vwap"],
            data["average"],
        ]
    market_data.minute_history[symbol].loc[ts] = new_data
    market_data.volume_today[symbol] = data["totalvolume"]

    if data["EV"] == "A":
        if (time_diff := datetime.now(tz=timezone("America/New_York")) - original_ts) > timedelta(seconds=8):  # type: ignore
            tlog(f"consumer A$ {symbol} out of sync w {time_diff}")
            return False
    elif data["EV"] == "AM":
        return True
    else:
        tlog(f"[ERROR] unknown EV {data['EV']}")

    # Next, check for existing orders for the stock
    existing_order = trading_data.open_orders.get(symbol)
    if existing_order is not None:
        existing_order = existing_order[0]
        try:
            if await should_cancel_order(existing_order, original_ts):
                inflight_order = await get_order(
                    trading_api, existing_order.id
                )
                if inflight_order and inflight_order.status == "filled":
                    tlog(
                        f"order_id {existing_order.id} for {symbol} already filled {inflight_order}"
                    )
                    await update_filled_order(
                        trading_data.open_order_strategy[symbol],
                        inflight_order,
                    )
                elif (
                    inflight_order
                    and inflight_order.status == "partially_filled"
                ):
                    tlog(
                        f"order_id {existing_order.id} for {symbol} already partially_filled {inflight_order}"
                    )
                    await update_partially_filled_order(
                        trading_data.open_order_strategy[symbol],
                        inflight_order,
                    )
                else:
                    # Cancel it so we can try again for a fill
                    tlog(
                        f"Cancel order id {existing_order.id} for {symbol} ts={original_ts} submission_ts={existing_order.submitted_at.astimezone(timezone('America/New_York'))}"
                    )
                    trading_api.cancel_order(existing_order.id)
                    trading_data.open_orders.pop(symbol, None)

            return True
        except AttributeError:
            error_logger.report_exception()
            tlog(f"Attribute Error in symbol {symbol} w/ {existing_order}")

    # do we have a position?
    symbol_position = trading_data.positions.get(symbol, 0)

    # do we need to liquidate for the day?
    until_market_close = config.market_close - ts
    if (
        until_market_close.seconds // 60
        <= config.market_liquidation_end_time_minutes
    ):
        await liquidate(symbol, symbol_position, trading_api)

    # run strategies
    for s in trading_data.strategies:
        do, what = await s.run(
            symbol,
            symbol_position,
            market_data.minute_history[symbol],
            ts,
            trading_api=trading_api,
        )

        if do:
            if what["type"] == "limit":
                o = trading_api.submit_order(
                    symbol=symbol,
                    qty=what["qty"],
                    side=what["side"],
                    type="limit",
                    time_in_force="day",
                    limit_price=what["limit_price"],
                )
            else:
                o = trading_api.submit_order(
                    symbol=symbol,
                    qty=what["qty"],
                    side=what["side"],
                    type=what["type"],
                    time_in_force="day",
                )

            trading_data.open_orders[symbol] = (o, what["side"])
            trading_data.open_order_strategy[symbol] = s
            trading_data.last_used_strategy[symbol] = s
            tlog(
                f"executed strategy {s.name} on {symbol} w data {market_data.minute_history[symbol][-10:]}"
            )
            continue

    return True


async def queue_consumer(queue: Queue, trading_api: tradeapi,) -> None:
    tlog("queue_consumer() starting")

    try:
        while True:
            raw_data = queue.get()
            data = json.loads(raw_data)
            # print(f"got {data}")
            if data["EV"] == "trade_update":
                tlog(f"received trade_update: {data}")
                await handle_trade_update(data)
            else:
                if not await handle_data_queue_msg(data, trading_api):
                    while not queue.empty():
                        _ = queue.get()
                    tlog("cleaned queue")

    except asyncio.CancelledError:
        tlog("queue_consumer() cancelled ")
    except Exception as e:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
        del exc_info
    finally:
        tlog("queue_consumer() task done.")


def get_trading_windows(tz, api):
    """Get start and end time for trading"""

    today = datetime.today().astimezone(tz)
    today_str = datetime.today().astimezone(tz).strftime("%Y-%m-%d")

    calendar = api.get_calendar(start=today_str, end=today_str)[0]

    tlog(f"next open date {calendar.date.date()}")

    if today.date() < calendar.date.date():
        tlog(f"which is not today {today}")
        return None, None
    market_open = today.replace(
        hour=calendar.open.hour,
        minute=calendar.open.minute,
        second=0,
        microsecond=0,
    )
    market_close = today.replace(
        hour=calendar.close.hour,
        minute=calendar.close.minute,
        second=0,
        microsecond=0,
    )
    return market_open, market_close


async def consumer_async_main(
    queue: Queue, symbols: List[str], unique_id: str
):
    await create_db_connection(str(config.dsn))

    base_url = (
        config.prod_base_url if config.env == "PROD" else config.paper_base_url
    )
    api_key_id = (
        config.prod_api_key_id
        if config.env == "PROD"
        else config.paper_api_key_id
    )
    api_secret = (
        config.prod_api_secret
        if config.env == "PROD"
        else config.paper_api_secret
    )
    trading_api = tradeapi.REST(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret
    )
    nyc = timezone("America/New_York")
    config.market_open, config.market_close = get_trading_windows(
        nyc, trading_api
    )

    strategy_types = [MomentumLong]
    for strategy_type in strategy_types:
        tlog(f"initializing {strategy_type.name}")
        s = strategy_type(batch_id=unique_id)
        await s.create()

        trading_data.strategies.append(s)

        if strategy_type == MomentumLong:
            await load_current_long_positions(trading_api, symbols, s)

    queue_consumer_task = asyncio.create_task(
        queue_consumer(queue, trading_api)
    )

    tear_down = asyncio.create_task(
        teardown_task(timezone("America/New_York"), queue_consumer_task)
    )
    await asyncio.gather(
        tear_down, queue_consumer_task, return_exceptions=True,
    )


async def load_current_long_positions(
    trading_api: tradeapi, symbols: List[str], strategy: Strategy
):
    for symbol in symbols:
        try:
            position = trading_api.get_position(symbol)
        except Exception:
            position = None

        if position:
            tlog(f"loading current position for {symbol}")
            try:
                (
                    prev_run_id,
                    price,
                    stop_price,
                    target_price,
                    indicators,
                ) = await NewTrade.load_latest_long(
                    config.db_conn_pool, symbol
                )

                trading_data.positions[symbol] = int(position.qty)
                trading_data.stop_prices[symbol] = stop_price
                trading_data.target_prices[symbol] = target_price
                trading_data.latest_cost_basis[symbol] = price
                trading_data.open_order_strategy[symbol] = strategy
                trading_data.last_used_strategy[symbol] = strategy
                trading_data.symbol_resistance[symbol] = indicators[
                    "resistances"
                ][0]

                await NewTrade.rename_algo_run_id(
                    strategy.algo_run.algo_run_id, prev_run_id, symbol
                )

            except Exception as e:
                tlog(
                    f"load_current_long_positions() for {symbol} could not load latest trade from db due to exception of type {type(e).__name__} with args {e.args}"
                )


def consumer_main(
    queue: Queue,
    symbols: List[str],
    minute_history: Dict[str, df],
    unique_id: str,
) -> None:
    tlog(f"*** consumer_main() starting w pid {os.getpid()} ***")

    config.build_label = pygit2.Repository("./").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )

    market_data.minute_history = minute_history
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(consumer_async_main(queue, symbols, unique_id))
        loop.run_forever()
    except KeyboardInterrupt:
        tlog("consumer_main() - Caught KeyboardInterrupt")

    tlog("*** consumer_main() completed ***")
