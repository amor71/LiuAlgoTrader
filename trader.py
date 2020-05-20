"""
Trading strategy runner
"""
import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List

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
from strategies.base import Strategy
from strategies.momentum_long import MomentumLong

# from strategies.momentum_short import MomentumShort

error_logger = error_reporting.Client()


async def liquidate(
    symbol: str,
    symbol_position: int,
    trading_api: tradeapi,
    data_ws: StreamConn,
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
    else:
        try:
            await data_ws.unsubscribe([f"A.{symbol}", f"AM.{symbol}"])
            # await trading_api.unsubscribe(trade_channels)
        except ValueError as e:
            tlog(f"failed to unsubscribe {symbol} w ValueError {e}")
            error_logger.report_exception()
        except Exception as e:
            tlog(f"failed to unsubscribe {symbol} w exception {e}")
            error_logger.report_exception()


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


async def second_task(
    queue: asyncio.Queue, trading_api: tradeapi, data_ws: StreamConn,
) -> None:
    tlog("second_task() starting")

    try:
        while True:
            data = await queue.get()
            symbol = data.symbol
            print(f"got[{symbol}]")

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

            if (now := datetime.now(tz=timezone("America/New_York"))) - data.start > timedelta(seconds=11):  # type: ignore
                tlog(
                    f"A$ {data.symbol} now={now} data.start={data.start} out of sync"
                )
                continue

            #        else:
            #            print(f"clock diff: {now-data.start}")

            # Next, check for existing orders for the stock
            existing_order = trading_data.open_orders.get(symbol)
            if existing_order is not None:
                existing_order = existing_order[0]
                try:
                    if await should_cancel_order(existing_order, original_ts):
                        inflight_order = await get_order(
                            trading_api, existing_order.id
                        )
                        if (
                            inflight_order
                            and inflight_order.status == "filled"
                        ):
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
                    continue
                except AttributeError:
                    error_logger.report_exception()
                    tlog(
                        f"Attribute Error in symbol {symbol} w/ {existing_order}"
                    )

            # do we have a position?
            symbol_position = trading_data.positions.get(symbol, 0)

            # do we need to liquidate for the day?
            until_market_close = config.market_close - ts
            if (
                until_market_close.seconds // 60
                <= config.market_liquidation_end_time_minutes
            ):
                await liquidate(symbol, symbol_position, trading_api, data_ws)

            # run strategies
            for s in trading_data.strategies:
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

    except asyncio.CancelledError:
        tlog("second_task() cancelled ")
    finally:
        tlog("second_task() task done.")


async def run(
    tickers: List[Ticker],
    data_api: tradeapi,
    trading_api: tradeapi,
    data_ws: StreamConn,
    trading_ws: StreamConn,
    data_ws2: StreamingBase,
    second_queue: asyncio.Queue,
) -> None:
    """main loop"""
    # Update initial state with information from tickers
    for ticker in tickers:
        symbol = ticker.ticker
        prev_closes[symbol] = ticker.prevDay["c"]
        volume_today[symbol] = ticker.day["v"]
    symbols = [ticker.ticker for ticker in tickers]
    tlog(f"Tracking {len(symbols)} symbols")

    market_data.minute_history = await get_historical_data(
        api=data_api,
        symbols=symbols,
        max_tickers=min(config.total_tickers, len(symbols)),
    )

    # Cancel any existing open orders on watched symbols
    existing_orders = trading_api.list_orders(limit=500)
    for order in existing_orders:
        if order.symbol in symbols:
            tlog(f"cancel open order of {order.symbol}")
            trading_api.cancel_order(order.id)

    # Track any positions bought during previous executions
    existing_positions = trading_api.list_positions()
    for position in existing_positions:
        if position.symbol in symbols:
            trading_data.positions[position.symbol] = float(position.qty)
            # Recalculate cost basis and stop price
            trading_data.latest_cost_basis[position.symbol] = float(
                position.cost_basis
            )

    # Keep track of what we're buying/selling
    trade_channels = ["trade_updates"]
    data_channels = []
    for symbol in symbols:
        symbol_channels = [
            f"{OP}.{symbol}" for OP in config.WS_DATA_CHANNELS
        ]  # ["A.{}".format(symbol), "AM.{}".format(symbol)]
        data_channels += symbol_channels

        if data_ws2:
            await data_ws2.subscribe(symbol, AlpacaStreaming.minutes_handler)
    tlog(f"Watching {len(symbols)} symbols.")

    # Use trade updates to keep track of our portfolio
    @trading_ws.on(r"trade_update")
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

    @data_ws.on(r"T$")
    async def handle_trade_event(conn, channel, data):
        # tlog(f"trade event: {conn} {channel} {data}")
        pass

    @data_ws.on(r"Q$")
    async def handle_quote_event(conn, channel, data):
        # tlog(f"quote event: {conn} {channel} {data}")
        pass

    @data_ws.on(r"A$")
    async def handle_second_bar(conn, channel, data):
        try:
            await second_queue.put(data)
        except Exception as e:
            tlog(f"Exception in handle_second_bar(): {e}")

    # Replace aggregated 1s bars with incoming 1m bars
    @data_ws.on(r"AM$")
    async def handle_minute_bar(conn, channel, data):
        # print(data)
        if datetime.now(tz=timezone("America/New_York")) - data.start > timedelta(seconds=11):  # type: ignore
            # tlog(
            #    f"AM$ {data.symbol} now={now} data.start={data.start} out of sync w {data}"
            # )
            pass
        ts = data.start
        ts = ts.replace(
            second=0, microsecond=0
        )  # ts -= timedelta(microseconds=ts.microsecond)

        market_data.minute_history[data.symbol].loc[ts] = [
            data.open,
            data.high,
            data.low,
            data.close,
            data.volume,
            data.vwap,
            data.average,
        ]
        volume_today[data.symbol] += data.volume

    await trading_ws.subscribe(trade_channels)
    await data_ws.subscribe(data_channels)


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


def motd(filename: str, version: str) -> None:
    """Display welcome message"""

    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"{filename} {version} starting")
    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"TRADE_BUY_WINDOW: {config.trade_buy_window}")
    tlog(f"DSN: {config.dsn}")
    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")


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
        hour=calendar.open.hour, minute=calendar.open.minute, second=0
    )
    market_close = today.replace(
        hour=calendar.close.hour, minute=calendar.close.minute, second=0
    )
    return market_open, market_close


async def off_hours_aggregates() -> None:
    tlog("starting to run off hours aggregates")
    await create_db_connection()
    await update_all_tickers_data()


async def main():
    trading_data.build_label = pygit2.Repository("./").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
    trading_data.filename = os.path.basename(__file__)
    motd(filename=trading_data.filename, version=trading_data.build_label)

    _data_api = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )
    nyc = timezone("America/New_York")
    config.market_open, config.market_close = get_trading_windows(
        nyc, _data_api
    )

    if config.market_open:
        tlog(
            f"markets open {config.market_open} market close {config.market_close}"
        )

        # Wait until just before we might want to trade
        current_dt = datetime.today().astimezone(nyc)
        tlog(f"current time {current_dt}")

        if current_dt < config.market_close or config.bypass_market_schedule:
            if not config.bypass_market_schedule:
                to_market_open = config.market_open - current_dt
                tlog(f"waiting for market open: {to_market_open}")
                if to_market_open.total_seconds() > 0:
                    try:
                        time.sleep(to_market_open.total_seconds() + 1)
                    except KeyboardInterrupt:
                        return
                tlog(
                    f"market open, wait {config.market_cool_down_minutes} minutes"
                )
                since_market_open = (
                    datetime.today().astimezone(nyc) - config.market_open
                )
                while (
                    since_market_open.seconds // 60
                    < config.market_cool_down_minutes
                ):
                    time.sleep(1)
                    since_market_open = (
                        datetime.today().astimezone(nyc) - config.market_open
                    )

            tlog("ready to start")
            base_url = (
                config.prod_base_url
                if config.env == "PROD"
                else config.paper_base_url
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

            _data_ws = tradeapi.StreamConn(
                base_url=config.prod_base_url,
                key_id=config.prod_api_key_id,
                secret_key=config.prod_api_secret,
                data_stream="polygon",
            )
            _alpaca_ws = AlpacaStreaming(
                key=config.prod_api_key_id, secret=config.prod_api_secret
            )
            await _alpaca_ws.connect()

            _trading_api = tradeapi.REST(
                base_url=base_url, key_id=api_key_id, secret_key=api_secret
            )
            _trade_ws = tradeapi.StreamConn(
                base_url=base_url, key_id=api_key_id, secret_key=api_secret,
            )
            tear_down = asyncio.create_task(
                teardown_task(nyc, [_trade_ws, _data_ws])
            )

            tlog("setting up strategies")
            await create_db_connection(str(config.dsn))

            strategy_types = [MomentumLong]
            for strategy_type in strategy_types:
                tlog(f"initializing {strategy_type.name}")
                s = strategy_type(trading_api=_trading_api, data_api=_data_api)
                await s.create()

                trading_data.strategies.append(s)

            tickers = await get_tickers(data_api=_data_api)

            _second_queue = asyncio.Queue()

            tlog("strategies ready to execute")

            main_task = asyncio.create_task(
                run(
                    tickers=tickers,
                    trading_api=_trading_api,
                    data_api=_data_api,
                    data_ws=_data_ws,
                    trading_ws=_trade_ws,
                    data_ws2=_alpaca_ws,
                    second_queue=_second_queue,
                )
            )

            seconds_worker = asyncio.create_task(
                second_task(
                    queue=_second_queue,
                    trading_api=_trading_api,
                    data_ws=_data_ws,
                )
            )
            await asyncio.gather(
                tear_down, main_task, seconds_worker, return_exceptions=True,
            )

        else:
            tlog(
                "missed market open time, try again next trading day, or bypass"
            )
    await off_hours_aggregates()


"""
starting
"""
try:
    asyncio.run(main())
except KeyboardInterrupt:
    tlog("main() - Caught KeyboardInterrupt")
except Exception as e:
    tlog(f"Caught exception {str(e)}")

tlog("Done.")
sys.exit(0)
