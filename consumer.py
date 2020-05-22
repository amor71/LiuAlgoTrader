import asyncio
from datetime import datetime, timedelta
from multiprocessing import Queue
from typing import Any, Dict, List

import alpaca_trade_api as tradeapi
import pygit2
from alpaca_trade_api.entity import Order
from alpaca_trade_api.polygon.entity import Ticker
from alpaca_trade_api.stream2 import StreamConn
from google.cloud import error_reporting
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from common import config, market_data, trading_data
from common.database import create_db_connection
from common.market_data import (get_historical_data, get_tickers, prev_closes,
                                volume_today)
from common.tlog import tlog
from data_stream.alpaca import AlpacaStreaming
from data_stream.streaming_base import StreamingBase
from market_miner import update_all_tickers_data
from models.new_trades import NewTrade
from producer import producer_main
from strategies.base import Strategy
from strategies.momentum_long import MomentumLong

# from strategies.momentum_short import MomentumShort

error_logger = error_reporting.Client()


async def trade_run(ws: StreamConn,) -> None:
    trade_channels = ["trade_updates"]

    # Use trade updates to keep track of our portfolio
    @ws.on(r"trade_update")
    async def handle_trade_update(conn, channel, data):
        symbol = data.order["symbol"]

        # if trade originated somewhere else, disregard
        if trading_data.open_orders.get(symbol) is None:
            return

        last_order = trading_data.open_orders.get(symbol)[0]
        if last_order is not None:
            tlog(f"trade update for {symbol} data={data}")
            event = data.event

            if event == "partial_fill":
                await update_partially_filled_order(
                    trading_data.open_order_strategy[symbol], Order(data.order)
                )
            elif event == "fill":
                await update_filled_order(
                    trading_data.open_order_strategy[symbol], Order(data.order)
                )
            elif event in ("canceled", "rejected"):
                trading_data.partial_fills.pop(symbol, None)
                trading_data.open_orders.pop(symbol, None)
                trading_data.open_order_strategy.pop(symbol, None)

        else:
            tlog(f"{data.event} trade update for {symbol} WITHOUT ORDER")

    await ws.subscribe(trade_channels)


async def end_time(reason: str):
    for s in trading_data.strategies:
        tlog(f"updating end time for strategy {s.name}")
        await s.algo_run.update_end_time(
            pool=trading_data.db_conn_pool, end_reason=reason
        )


async def teardown_task(tz: DstTzInfo, ws: List[StreamConn]) -> None:
    dt = datetime.today().astimezone(tz)
    to_market_close = (
        config.market_close - dt
        if config.market_close > dt
        else timedelta(hours=24) + (config.market_close - dt)
    )

    tlog(f"tear-down task waiting for market close: {to_market_close}")
    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 10)
    except asyncio.CancelledError:
        tlog("teardown_task() cancelled during sleep")
    else:
        tlog("tear down task starting")
        await end_time("market close")

        tlog("closing web-sockets")
        for w in ws:
            await w.close()

        asyncio.get_running_loop().stop()
    finally:
        tlog("tear down task done.")


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
        trading_data.db_conn_pool,
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

    await save(
        order.symbol,
        new_qty,
        trading_data.open_orders.get(order.symbol)[1],
        float(order.filled_avg_price),
        trading_data.buy_indicators[order.symbol]
        if order.side == "buy"
        else trading_data.sell_indicators[order.symbol],
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

    trading_data.open_orders[order.symbol] = None
    trading_data.open_order_strategy[order.symbol] = None


async def handle_queue_msg(data: Any, trading_api: tradeapi) -> bool:
    symbol = data.symbol
    print(f"got [{symbol}] to handle_queue_msg")

    # First, aggregate 1s bars for up-to-date MACD calculations
    original_ts = ts = data.start
    ts = ts.replace(
        second=0, microsecond=0
    )  # timedelta(seconds=ts.second, microseconds=ts.microsecond)

    try:
        current = market_data.minute_history[data.symbol].loc[ts]
    except KeyError:
        current = None

    if current is None:
        new_data = [
            data.open,
            data.high,
            data.low,
            data.close,
            data.volume,
            data.vwap,
            data.average,
        ]
    else:
        new_data = [
            current.open,
            data.high if data.high > current.high else current.high,
            data.low if data.low < current.low else current.low,
            data.close,
            current.volume + data.volume,
            data.vwap,
            data.average,
        ]
    market_data.minute_history[symbol].loc[ts] = new_data

    """
    if (now := datetime.now(tz=timezone("America/New_York"))) - data.start > timedelta(seconds=6):  # type: ignore
        # tlog(f"A$ {data.symbol} now={now} data.start={data.start} out of sync")
        return False
    """

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
                        f"Cancel order id {existing_order.id} for {symbol} ts={original_ts} submission_ts={existing_order.submitted_at}"
                    )
                    trading_api.cancel_order(existing_order.id)
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
        try:
            if await s.run(
                symbol,
                symbol_position,
                market_data.minute_history[symbol],
                ts,
            ):
                trading_data.last_used_strategy[symbol] = s
                tlog(
                    f"executed strategy {s.name} on {symbol} w data {market_data.minute_history[symbol][-10:]}"
                )
                continue
        except Exception as e:
            tlog(
                f"handle_queue_msg() exception of type {type(e).__name__} with args {e.args} for {symbol}"
            )

    return True


async def queue_consumer(queue: Queue, trading_api: tradeapi,) -> None:
    tlog("queue_consumer() starting")

    try:
        while True:
            data = await queue.get()
            asyncio.create_task(handle_queue_msg(data, trading_api))

    except asyncio.CancelledError:
        tlog("queue_consumer() cancelled ")
    finally:
        tlog("queue_consumer() task done.")


async def consumer_async_main(queue: Queue):
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

    strategy_types = [MomentumLong]
    for strategy_type in strategy_types:
        tlog(f"initializing {strategy_type.name}")
        s = strategy_type(trading_api=trading_api)
        await s.create()

        trading_data.strategies.append(s)

    trade_ws = tradeapi.StreamConn(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret,
    )

    trade_task = asyncio.create_task(trade_run(ws=trade_ws))

    queue_consumer_task = asyncio.create_task(
        queue_consumer(queue, trading_api)
    )

    tear_down = asyncio.create_task(
        teardown_task(timezone("America/New_York"), [trade_ws])
    )
    await asyncio.gather(
        tear_down, trade_task, queue_consumer_task, return_exceptions=True,
    )


def consumer_main(queue: Queue, symbols: List[str]) -> None:
    tlog("*** consumer_main() starting ***")
    trading_data.build_label = pygit2.Repository("./").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
    try:
        asyncio.run(asyncio.run(consumer_async_main(queue)))
    except KeyboardInterrupt:
        tlog("consumer_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"consumer_main() - exception of type {type(e).__name__} with args {e.args}"
        )
        raise

    tlog("*** consumer_main() completed ***")
