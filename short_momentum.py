"""
Short Momentum Trading Algorithm
"""
import asyncio
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import asyncpg
import numpy as np
import pygit2
import requests
from alpaca_trade_api.entity import Order
from asyncpg.pool import Pool
from google.cloud import error_reporting, logging
from pytz import timezone
from pytz.tzinfo import DstTzInfo
from talib import MACD, RSI

import config
from market_data import get_historical_data, get_tickers
from models.algo_run import AlgoRun
from models.new_trades import NewTrade
from support_resistance import find_resistances, find_supports

client = logging.Client()
logger = client.logger("short_momentum")
error_logger = error_reporting.Client()

# Replace these with your API connection info from the dashboard
paper_base_url = "https://paper-api.alpaca.markets"
paper_api_key_id = "PKO3OSD9LU9GTQPL69GO"
paper_api_secret = "chnPFlGXbY4Y4QAAZ3Q7MJHxkxBYB30CQZNVZTaj"

prod_base_url = "https://api.alpaca.markets"
prod_api_key_id = "AKVKN4TLUUS5MZO5KYLM"
prod_api_secret = "nkK2UmvE1kTFFw1ZlaqDmwCyiuCu7OOeB5y2La/X"

session = requests.session()
symbols: List[str] = []
minute_history: Dict[str, object] = {}
volume_today = {}
prev_closes = {}
buy_indicators: Dict[str, Dict] = {}
sell_indicators: Dict[str, Dict] = {}
env = os.getenv("TRADE", "PAPER")
dsn = os.getenv("DSN", None)
trade_channels = ["trade_updates"]
data_channels = []
data_conn = None
trade_conn = None
db_conn_pool: Pool
run_details = None
strategy_name: str
resistances: Dict[str, List] = {}


def run(
    tickers,
    market_open_dt,
    market_close_dt,
    api,
    prod_api,
    base_url,
    api_key_id,
    api_secret,
    trade_buy_window,
):
    """main loop"""

    if tickers is None:
        return

    global env
    global data_conn
    global trade_conn
    global symbols
    global minute_history
    global volume_today
    global prev_closes
    global data_channels
    global trade_channels
    global strategy_name

    # Establish streaming connection
    trade_conn = tradeapi.StreamConn(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret,
    )
    data_conn = tradeapi.StreamConn(
        base_url=prod_base_url,
        key_id=prod_api_key_id,
        secret_key=prod_api_secret,
    )
    # Update initial state with information from tickers
    for ticker in tickers:
        symbol = ticker.ticker
        prev_closes[symbol] = ticker.prevDay["c"]
        volume_today[symbol] = ticker.day["v"]
    symbols = [ticker.ticker for ticker in tickers]
    logger.log_text(
        "[{}][{}] Tracking {} symbols.".format(
            env, strategy_name, len(symbols)
        )
    )
    minute_history = get_historical_data(
        my_logger=logger,
        env=env,
        strategy_name=strategy_name,
        api=prod_api,
        symbols=symbols,
    )

    portfolio_value = float(api.get_account().portfolio_value)

    open_orders = {}
    positions = {}

    # Cancel any existing open orders on watched symbols
    existing_orders = api.list_orders(limit=500)
    for order in existing_orders:
        if order.symbol in symbols:
            logger.log_text(
                f"[{env}][{strategy_name}] cancel open order of {order.symbol}"
            )
            api.cancel_order(order.id)

    stop_prices = {}
    latest_cost_basis = {}

    # Track any positions bought during previous executions
    existing_positions = api.list_positions()
    for position in existing_positions:
        if position.symbol in symbols:
            positions[position.symbol] = float(position.qty)
            # Recalculate cost basis and stop price
            latest_cost_basis[position.symbol] = float(position.cost_basis)
            stop_prices[position.symbol] = (
                float(position.cost_basis) * config.default_stop
            )

    # Keep track of what we're buying/selling
    target_prices = {}
    partial_fills = {}

    for symbol in symbols[:80]:
        symbol_channels = ["A.{}".format(symbol), "AM.{}".format(symbol)]
        data_channels += symbol_channels
    logger.log_text(
        "[{}][{}] Watching {} symbols.".format(
            env, strategy_name, len(symbols)
        )
    )

    # Use trade updates to keep track of our portfolio
    @trade_conn.on(r"trade_update")
    async def handle_trade_update(conn, channel, data):
        global env
        global run_details
        global buy_indicators
        global db_conn_pool
        global strategy_name

        symbol = data.order["symbol"]
        last_order = open_orders.get(symbol)
        if last_order is not None:
            logger.log_text(
                f"[{env}][{strategy_name}] {data.event} trade update for {symbol}"
            )
            event = data.event
            if event == "partial_fill":
                qty = int(data.order["filled_qty"])
                if data.order["side"] == "sell":
                    qty = qty * -1
                positions[symbol] = positions.get(
                    symbol, 0
                ) - partial_fills.get(symbol, 0)
                partial_fills[symbol] = qty
                positions[symbol] += qty
                open_orders[symbol] = Order(data.order)
            elif event == "fill":
                qty = int(data.order["filled_qty"])
                if data.order["side"] == "sell":
                    qty = qty * -1
                positions[symbol] = positions.get(
                    symbol, 0
                ) - partial_fills.get(symbol, 0)
                partial_fills[symbol] = 0
                positions[symbol] += qty

                if data.order["side"] == "buy":
                    print(data.order)
                    db_trade = NewTrade(
                        algo_run_id=run_details.algo_run_id,
                        symbol=symbol,
                        qty=qty,
                        operation="buy",
                        price=float(data.order["filled_avg_price"]),
                        indicators=buy_indicators[symbol],
                    )
                    await db_trade.save(
                        db_conn_pool,
                        data.timestamp,
                        stop_prices[symbol],
                        target_prices[symbol],
                    )
                    buy_indicators[symbol] = None
                if data.order["side"] == "sell":
                    if sell_indicators[symbol] is not None:
                        db_trade = NewTrade(
                            algo_run_id=run_details.algo_run_id,
                            symbol=symbol,
                            qty=-qty,
                            operation="sell",
                            price=float(data.order["filled_avg_price"]),
                            indicators=sell_indicators[symbol],
                        )
                        await db_trade.save(
                            db_conn_pool,
                            data.timestamp,
                            stop_prices[symbol],
                            target_prices[symbol],
                        )
                    sell_indicators[symbol] = None

                open_orders[symbol] = None
            elif event in ("canceled", "rejected"):
                partial_fills[symbol] = 0
                open_orders[symbol] = None
        else:
            logger.log_text(
                f"[{env}][{strategy_name}] {data.event} trade update for {symbol} WITHOUT ORDER"
            )

    @data_conn.on(r"A$")
    async def handle_second_bar(conn, channel, data):
        global env
        global strategy_name
        symbol = data.symbol

        # First, aggregate 1s bars for up-to-date MACD calculations
        original_ts = ts = data.start
        ts = ts.replace(
            second=0, microsecond=0
        )  # timedelta(seconds=ts.second, microseconds=ts.microsecond)
        since_market_open = ts - market_open_dt
        until_market_close = market_close_dt - ts

        try:
            current = minute_history[data.symbol].loc[ts]
        except KeyError:
            current = None

        if current is None:
            new_data = [
                data.open,
                data.high,
                data.low,
                data.close,
                data.volume,
            ]
        else:
            new_data = [
                current.open,
                data.high if data.high > current.high else current.high,
                data.low if data.low < current.low else current.low,
                data.close,
                current.volume + data.volume,
            ]
        minute_history[symbol].loc[ts] = new_data

        # Next, check for existing orders for the stock
        existing_order = open_orders.get(symbol)
        if existing_order is not None:
            try:
                # Make sure the order's not too old
                submission_ts = existing_order.submitted_at.astimezone(
                    timezone("America/New_York")
                )
                order_lifetime = original_ts - submission_ts
                if (
                    original_ts > submission_ts
                    and order_lifetime.seconds // 60 >= 1
                ):
                    # Cancel it so we can try again for a fill
                    logger.log_text(
                        f"[{env}][{strategy_name}] Cancel order id {existing_order.id} for {symbol} ts={original_ts} submission_ts={submission_ts}"
                    )
                    api.cancel_order(existing_order.id)
                return
            except AttributeError:
                error_logger.report_exception()
                logger.log_text(
                    f"[{env}][{strategy_name}] Attribute Error in symbol {symbol} w/ {existing_order}"
                )

        # Now we check to see if it might be time to buy or sell

        # do we have a position?
        symbol_position = positions.get(symbol, 0)
        if (
            trade_buy_window > since_market_open.seconds // 60 > 15
            and not symbol_position
        ):
            # Check for buy signals
            # See how high the price went during the first 15 minutes
            lbound = market_open_dt
            ubound = lbound + timedelta(minutes=15)
            try:
                high_15m = minute_history[symbol][lbound:ubound]["high"].max()
            except Exception:
                error_logger.report_exception()
                # Because we're aggregating on the fly, sometimes the datetime
                # index can get messy until it's healed by the minute bars
                return

            # Get the change since yesterday's market close
            daily_pct_change = (
                data.close - prev_closes[symbol]
            ) / prev_closes[symbol]
            if (
                daily_pct_change > 0.04
                and data.close > high_15m
                and volume_today[symbol] > 30000
            ):
                logger.log_text(
                    f"[{env}][{strategy_name}] {symbol} high_15m={high_15m} data.close={data.close}"
                )
                # check for a positive, increasing MACD
                macds = MACD(
                    minute_history[symbol]["close"]
                    .dropna()
                    .between_time("9:30", "16:00")
                )

                sell_macds = MACD(
                    minute_history[symbol]["close"]
                    .dropna()
                    .between_time("9:30", "16:00"),
                    13,
                    21,
                )

                macd1 = macds[0]
                macd_signal = macds[1]
                if (
                    macd1[-1].round(2) > 0
                    and macd1[-3].round(3)
                    < macd1[-2].round(3)
                    < macd1[-1].round(3)
                    and macd1[-1].round(2) > macd_signal[-1].round(2)
                    and sell_macds[0][-1] > 0
                    and data.close > new_data[0]
                    # and 0 < macd1[-2] - macd1[-3] < macd1[-1] - macd1[-2]
                ):
                    logger.log_text(
                        f"[{env}][{strategy_name}] MACD(12,26) for {symbol} trending up!, MACD(13,21) trending up and above signals"
                    )
                    macd2 = MACD(
                        minute_history[symbol]["close"]
                        .dropna()
                        .between_time("9:30", "16:00"),
                        40,
                        60,
                    )[0]
                    if macd2[-1] >= 0 and np.diff(macd2)[-1] >= 0:
                        logger.log_text(
                            f"[{env}][{strategy_name}] MACD(40,60) for {symbol} trending up!"
                        )
                        # check RSI does not indicate overbought
                        rsi = RSI(minute_history[symbol]["close"], 14)
                        logger.log_text(
                            f"[{env}][{strategy_name}] RSI {rsi[-1]} "
                        )
                        if rsi[-1] > 65:

                            supports = find_supports(
                                logger=logger,
                                env=env,
                                strategy_name=strategy_name,
                                current_value=data.close,
                                minute_history=minute_history[symbol],
                                now=ts,
                            )
                            resistances = find_resistances(
                                logger=logger,
                                env=env,
                                strategy_name=strategy_name,
                                current_value=data.close,
                                minute_history=minute_history[symbol],
                                now=ts,
                            )
                            if supports is None or supports == []:
                                logger.log_text(
                                    f"[{env}][{strategy_name}] no supports for {symbol} -> skip short buy"
                                )
                                return

                            if resistances is None or resistances == []:
                                logger.log_text(
                                    f"[{env}][{strategy_name}] no resistances for {symbol} -> skip short buy"
                                )
                                return

                            stop_prices[symbol] = resistances[0]
                            target_prices[symbol] = supports[-1]
                            shares_to_buy = (
                                portfolio_value
                                * config.risk
                                // (stop_prices[symbol] - data.close)
                            )
                            if not shares_to_buy:
                                shares_to_buy = 1
                            shares_to_buy -= positions.get(symbol, 0)
                            if shares_to_buy > 0:
                                logger.log_text(
                                    "[{}][{}] Submitting short sell for {} shares of {} at {} target {} stop {}".format(
                                        env,
                                        strategy_name,
                                        shares_to_buy,
                                        symbol,
                                        data.close,
                                        target_prices[symbol],
                                        stop_prices[symbol],
                                    )
                                )
                                try:
                                    buy_indicators[symbol] = {
                                        "rsi": rsi[-1].tolist(),
                                        "macd": macd1[-5:].tolist(),
                                        "macd_signal": macd_signal[
                                            -5:
                                        ].tolist(),
                                        "slow macd": macd2[-5:].tolist(),
                                        "sell_macd": sell_macds[0][
                                            -5:
                                        ].tolist(),
                                        "sell_macd_signal": sell_macds[1][
                                            -5:
                                        ].tolist(),
                                    }
                                    o = api.submit_order(
                                        symbol=symbol,
                                        qty=str(shares_to_buy),
                                        side="sell",
                                        type="market",
                                        time_in_force="day",
                                    )
                                    open_orders[symbol] = o
                                    latest_cost_basis[symbol] = data.close
                                    return
                                    pass
                                except Exception:
                                    error_logger.report_exception()
                    else:
                        logger.log_text(
                            f"[{env}][{strategy_name}] failed MACD(40,60) for {symbol}!"
                        )

        if (
            since_market_open.seconds // 60 >= 15
            and until_market_close.seconds // 60 > 15
            and symbol_position > 0
        ):
            # Check for liquidation signals
            # Sell for a loss if it's fallen below our stop price
            # Sell for a loss if it's below our cost basis and MACD < 0
            # Sell for a profit if it's above our target price
            macds = MACD(
                minute_history[symbol]["close"]
                .dropna()
                .between_time("9:30", "16:00"),
                13,
                21,
            )

            macd = macds[0]
            macd_signal = macds[1]
            rsi = RSI(minute_history[symbol]["close"], 14)
            movement = (
                data.close - latest_cost_basis[symbol]
            ) / latest_cost_basis[symbol]

            to_sell = False
            sell_reasons = []
            if data.close >= stop_prices[symbol]:
                to_sell = True
                sell_reasons.append(f"stopped")
            elif data.close <= target_prices[symbol]:
                to_sell = True
                sell_reasons.append(f"target")

            if to_sell:
                try:
                    sell_indicators[symbol] = {
                        "rsi": rsi[-1].tolist(),
                        "movement": movement,
                        "sell_macd": macd[-5:].tolist(),
                        "sell_macd_signal": macd_signal[-5:].tolist(),
                        "reasons": " AND ".join(
                            [str(elem) for elem in sell_reasons]
                        ),
                    }

                    logger.log_text(
                        "[{}][{}] Submitting short buy for {} shares of {} at market".format(
                            env, strategy_name, symbol_position, symbol
                        )
                    )
                    o = api.submit_order(
                        symbol=symbol,
                        qty=str(symbol_position),
                        side="buy",
                        type="market",
                        time_in_force="day",
                    )

                    open_orders[symbol] = o
                    latest_cost_basis[symbol] = data.close
                    return
                except Exception:
                    error_logger.report_exception()

        if until_market_close.seconds // 60 <= 15:
            logger.log_text(
                f"[{env}][{strategy_name}] {until_market_close.seconds // 60} minutes to market close for {symbol}"
            )
            if symbol_position:
                logger.log_text(
                    "[{}][{}] Trading over, trying to liquidating remaining position in {}".format(
                        env, strategy_name, symbol
                    )
                )
                try:
                    sell_indicators[symbol] = {
                        "rsi": 0,
                        "data.close <= stop_prices": 0,
                        "macd": [],
                        "data.close >= target_prices": 0,
                        "macd_signal": [],
                        "too_close": 0,
                        "distance_macd_to_signal_macd": 0,
                        "bail_out": 0,
                    }
                    o = api.submit_order(
                        symbol=symbol,
                        qty=str(symbol_position),
                        side="buy",
                        type="market",
                        time_in_force="day",
                    )
                    open_orders[symbol] = o
                    latest_cost_basis[symbol] = data.close
                except Exception:
                    error_logger.report_exception()
                return

            logger.log_text(
                f"[{env}][{strategy_name}] unsubscribe channels for {symbol}"
            )
            try:
                if symbol in symbol:
                    symbols.remove(symbol)
                await data_conn.unsubscribe([f"A.{symbol}", f"AM.{symbol}"])
                await trade_conn.unsubscribe(trade_channels)
                logger.log_text(
                    f"[{env}][{strategy_name}] {len(symbols)} channels left"
                )
            except ValueError:
                pass
            except Exception:
                error_logger.report_exception()

    # Replace aggregated 1s bars with incoming 1m bars
    @data_conn.on(r"AM$")
    async def handle_minute_bar(conn, channel, data):
        ts = data.start
        ts -= timedelta(microseconds=ts.microsecond)
        minute_history[data.symbol].loc[ts] = [
            data.open,
            data.high,
            data.low,
            data.close,
            data.volume,
        ]
        volume_today[data.symbol] += data.volume

    run_ws(
        base_url,
        api_key_id,
        api_secret,
        trade_conn,
        data_conn,
        trade_channels,
        data_channels,
    )


def run_ws(
    base_url,
    api_key_id,
    api_secret,
    trade_conn,
    data_conn,
    trade_channels,
    data_channels,
):
    global strategy_name
    """Handle failed websocket connections by reconnecting"""
    logger.log_text(f"[{env}][{strategy_name}] starting web-socket loop")

    try:
        trade_conn.loop.run_until_complete(
            trade_conn.subscribe(trade_channels)
        )
        data_conn.loop.run_until_complete(data_conn.subscribe(data_channels))
        data_conn.loop.run_forever()
    except Exception as e:
        print(str(e))
        error_logger.report_exception()


async def save_start(
    name: str, environment: str, build: str, parameters: dict
):
    global strategy_name
    logger.log_text(f"[{env}][{strategy_name}] save_start task starting")
    global run_details
    run_details = AlgoRun(name, environment, build, parameters)
    await set_db_connection(str(dsn))
    global db_conn_pool
    await run_details.save(pool=db_conn_pool)
    logger.log_text(f"[{env}][{strategy_name}] save_start task ended")


async def teardown_task(tz: DstTzInfo, market_close: datetime):
    global strategy_name
    dt = datetime.today().astimezone(tz)
    to_market_close = market_close - dt

    logger.log_text(
        f"[{env}][{strategy_name}] tear-down task waiting for market close: {to_market_close}"
    )
    print(f"tear down waiting for market close: {to_market_close}")

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 10)
    except asyncio.CancelledError:
        print("teardown_task() cancelled during sleep")
        logger.log_text(
            f"[{strategy_name}]teardown_task() cancelled during sleep"
        )
    else:
        logger.log_text(f"[{strategy_name}]tear down task starting")
        print("tear down task starting")
        await end_time("market close")
        asyncio.get_running_loop().stop()
    finally:
        logger.log_text(f"[{env}][{strategy_name}]tear down task done.")
        print("tear down task done.")


async def end_time(reason: str):
    global run_details
    global db_conn_pool
    if run_details is not None:
        await run_details.update_end_time(pool=db_conn_pool, end_reason=reason)


async def set_db_connection(dsn: str):
    global db_conn_pool
    db_conn_pool = await asyncpg.create_pool(
        dsn=dsn, min_size=20, max_size=200
    )


def main():
    r = pygit2.Repository("./")
    label = r.describe()
    filename = os.path.basename(__file__)
    global strategy_name
    strategy_name = filename
    msg = f"{filename} {label} starting!"
    logger.log_text(msg)
    print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
    print(msg)
    print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
    trade_buy_window = int(os.getenv("TRADE_BUY_WINDOW", "120"))
    print(f"TRADE environment {env}")
    print(f"TRADE_BUY_WINDOW {trade_buy_window}")
    print(f"DSN: {dsn}")
    print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")

    base_url = prod_base_url if env == "PROD" else paper_base_url
    api_key_id = prod_api_key_id if env == "PROD" else paper_api_key_id
    api_secret = prod_api_secret if env == "PROD" else paper_api_secret

    api = tradeapi.REST(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret
    )
    prod_api = tradeapi.REST(
        base_url=prod_base_url,
        key_id=prod_api_key_id,
        secret_key=prod_api_secret,
    )
    # Get when the market opens or opened today
    nyc = timezone("America/New_York")
    today = datetime.today().astimezone(nyc)
    today_str = datetime.today().astimezone(nyc).strftime("%Y-%m-%d")
    calendar = prod_api.get_calendar(start=today_str, end=today_str)[0]
    market_open = today.replace(
        hour=calendar.open.hour, minute=calendar.open.minute, second=0
    )
    logger.log_text(f"[{env}] markets open {market_open}")
    print(f"markets open {market_open}")
    market_open = market_open.astimezone(nyc)
    market_close = today.replace(
        hour=calendar.close.hour, minute=calendar.close.minute, second=0
    )
    market_close = market_close.astimezone(nyc)
    logger.log_text(f"[{env}] markets close {market_close}")
    print(f"markets close {market_close}")

    # Wait until just before we might want to trade
    current_dt = datetime.today().astimezone(nyc)
    logger.log_text(f"[{env}] current time {current_dt}")

    if current_dt < market_close:
        to_market_open = market_open - current_dt
        logger.log_text(f"[{env}] waiting for market open: {to_market_open}")
        print(f"waiting for market open: {to_market_open}")

        if to_market_open.total_seconds() > 0:
            time.sleep(to_market_open.total_seconds() + 1)

        logger.log_text(f"[{env}] market open! wait ~14 minutes")
        since_market_open = datetime.today().astimezone(nyc) - market_open
        while since_market_open.seconds // 60 <= 14:
            time.sleep(1)
            since_market_open = datetime.today().astimezone(nyc) - market_open

        logger.log_text(f"[{env}] ready to start!")
        print("ready to start!")
        asyncio.ensure_future(
            save_start(
                filename,
                env,
                label,
                {"TRADE_BUY_WINDOW": trade_buy_window, "DSN": dsn},
            )
        )
        asyncio.ensure_future(teardown_task(nyc, market_close))
        run(
            get_tickers(
                my_logger=logger,
                env=env,
                strategy_name=strategy_name,
                api=prod_api,
            ),
            market_open,
            market_close,
            api,
            prod_api,
            base_url,
            api_key_id,
            api_secret,
            trade_buy_window,
        )
    else:
        logger.log_text(
            f"[{env}] OH, missed the entry time, try again next trading day"
        )
        print("OH, missed the entry time, try again next trading day")


"""
starting
"""
try:
    main()
except KeyboardInterrupt:
    print(f"Caught KeyboardInterrupt")
    asyncio.get_event_loop().run_until_complete(end_time("KeyboardInterrupt"))
except Exception as e:
    print(f"Caught exception {str(e)}")
    asyncio.get_event_loop().run_until_complete(end_time(str(e)))

logger.log_text(f"[{env}] Done.")
print("Done.")
