"""
Momentum Trading Algorithm
"""
import asyncio
import os
import time
from datetime import date, datetime, timedelta
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

from models.algo_run import AlgoRun
from models.new_trades import NewTrade

client = logging.Client()
logger = client.logger("algo")
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

# We only consider stocks with per-share prices inside this range
min_share_price = 2.0
max_share_price = 20.0
# Minimum previous-day dollar volume for a stock we might consider
min_last_dv = 500000
# Stop limit to default to
default_stop = 0.95
# How much of our portfolio to allocate to any one position
risk = 0.001


def grouper(iterable):
    prev = None
    group = []
    for item in iterable:

        if not prev or -0.01 <= float(item - prev) / prev <= 0.01:
            group.append(item)
        else:
            yield group
            group = [item]
        prev = item
    if group:
        yield group


def find_resistance(current_value, minute_history, now):
    """calculate next resistance"""
    minute_history_index = minute_history["high"].index.get_loc(
        now, method="nearest"
    )
    series = (
        minute_history["high"][
            minute_history_index - 200 : minute_history_index
        ]
        .dropna()
        .resample("5min")
        .min()
    )
    print(f"current_value={current_value} series = {series.values}")
    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] > current_value]
        )
        print(local_maximas)
        clusters = dict(enumerate(grouper(local_maximas), 1))
        print(clusters)
        resistances = []
        for key, cluster in clusters.items():
            if len(cluster) > 1:
                resistances.append(round(sum(cluster) / len(cluster), 2))
        resistances = sorted(resistances)
        print(f"resistances={resistances}")
        return resistances

    return None


def find_support(current_value, minute_history, now):
    """calculate support"""
    minute_history_index = minute_history["high"].index.get_loc(
        now, method="nearest"
    )
    series = (
        minute_history["high"][
            minute_history_index - 200 : minute_history_index
        ]
        .dropna()
        .resample("5min")
        .min()
    )
    print(f"current_value={current_value} series = {series.values}")
    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] <= current_value]
        )
        print(local_maximas)
        clusters = dict(enumerate(grouper(local_maximas), 1))
        print(clusters)
        supports = []
        for key, cluster in clusters.items():
            if len(cluster) > 1:
                supports.append(round(sum(cluster) / len(cluster), 2))
        supports = sorted(supports)
        print(f"supports={supports}")
        return supports

    return None


def get_1000m_history_data(api):
    """get ticker history"""
    global env
    global minute_history
    global symbols
    logger.log_text(f"[{env}] Getting historical data...")
    c = 0
    exclude_symbols = []
    for symbol in symbols:
        if symbol not in minute_history:
            retry_counter = 5
            while retry_counter > 0:
                try:
                    minute_history[symbol] = api.polygon.historic_agg_v2(
                        symbol,
                        1,
                        "minute",
                        _from=date.today() - timedelta(days=10),
                        to=date.today() + timedelta(days=1),
                    ).df
                    break
                except (
                    requests.exceptions.HTTPError,
                    requests.exceptions.ConnectionError,
                ):
                    retry_counter -= 1
                    if retry_counter == 0:
                        error_logger.report_exception()
                        exclude_symbols.append(symbol)
            c += 1
            logger.log_text(f"[{env}] {symbol} {c}/{len(symbols)}")

    for x in exclude_symbols:
        symbols.remove(x)


def get_tickers(api):
    """get all tickets"""
    global env
    logger.log_text(f"[{env}] Getting current ticker data...")
    max_retries = 5
    while max_retries > 0:
        tickers = api.polygon.all_tickers()
        assets = api.list_assets()
        tradable_symbols = [asset.symbol for asset in assets if asset.tradable]
        rc = [
            ticker
            for ticker in tickers
            if (
                ticker.ticker in tradable_symbols
                and max_share_price >= ticker.lastTrade["p"] >= min_share_price
                and ticker.prevDay["v"] * ticker.lastTrade["p"] > min_last_dv
                and ticker.todaysChangePerc >= 3.5
            )
        ]
        if len(rc) > 0:
            return rc

        logger.log_text(f"[{env}] got no data :-( waiting then re-trying")
        print("no tickers :-( waiting and retrying")
        time.sleep(30)
        max_retries -= 1

    logger.log_text(f"[{env}] got no data :-( giving up")
    print("got no data :-( giving up")
    return None


def find_stop(current_value, minute_history, now):
    """calculate stop loss"""
    series = minute_history["low"][-100:].dropna().resample("5min").min()
    series = series[now.floor("1D") :]
    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(low_index) > 0:
        return series[low_index[-1]] - 0.01
    return current_value * default_stop


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
    logger.log_text("[{}] Tracking {} symbols.".format(env, len(symbols)))
    get_1000m_history_data(prod_api)

    portfolio_value = float(api.get_account().portfolio_value)

    open_orders = {}
    positions = {}

    # Cancel any existing open orders on watched symbols
    existing_orders = api.list_orders(limit=500)
    for order in existing_orders:
        if order.symbol in symbols:
            logger.log_text(f"[{env}] cancel open order of {order.symbol}")
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
                float(position.cost_basis) * default_stop
            )

    # Keep track of what we're buying/selling
    target_prices = {}
    partial_fills = {}

    for symbol in symbols[:80]:
        symbol_channels = ["A.{}".format(symbol), "AM.{}".format(symbol)]
        data_channels += symbol_channels
    logger.log_text("[{}] Watching {} symbols.".format(env, len(symbols)))

    # Use trade updates to keep track of our portfolio
    @trade_conn.on(r"trade_update")
    async def handle_trade_update(conn, channel, data):
        global env
        global run_details
        global buy_indicators
        global db_conn_pool

        symbol = data.order["symbol"]
        last_order = open_orders.get(symbol)
        if last_order is not None:
            logger.log_text(f"[{env}] {data.event} trade update for {symbol}")
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
                f"[{env}] {data.event} trade update for {symbol} WITHOUT ORDER"
            )

    @data_conn.on(r"A$")
    async def handle_second_bar(conn, channel, data):
        global env
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
                        f"[{env}] Cancel order id {existing_order.id} for {symbol} ts={original_ts} submission_ts={submission_ts}"
                    )
                    api.cancel_order(existing_order.id)
                return
            except AttributeError:
                error_logger.report_exception()
                logger.log_text(
                    f"[{env}] Attribute Error in symbol {symbol} w/ {existing_order}"
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
                    f"[{env}] {symbol} high_15m={high_15m} data.close={data.close}"
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
                        f"[{env}] MACD(12,26) for {symbol} trending up!, MACD(13,21) trending up and above signals"
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
                            f"[{env}] MACD(40,60) for {symbol} trending up!"
                        )
                        # check RSI does not indicate overbought
                        rsi = RSI(minute_history[symbol]["close"], 14)

                        if rsi[-1] < 80:
                            logger.log_text(f"[{env}] RSI {rsi[-1]} < 80")
                            resistance = find_resistance(
                                data.close, minute_history[symbol], ts
                            )

                            if resistance is None or resistance == []:
                                logger.log_text(
                                    f"[{env}] no resistance for {symbol} -> skip buy"
                                )
                                return

                            # Stock has passed all checks; figure out how much to buy
                            stop_price = find_stop(
                                data.close, minute_history[symbol], ts
                            )
                            stop_prices[symbol] = stop_price
                            target_prices[symbol] = (
                                data.close + (data.close - stop_price) * 3
                            )
                            shares_to_buy = (
                                portfolio_value
                                * risk
                                // (data.close - stop_price)
                            )
                            if not shares_to_buy:
                                shares_to_buy = 1
                            shares_to_buy -= positions.get(symbol, 0)
                            if shares_to_buy > 0:
                                logger.log_text(
                                    "[{}] Submitting buy for {} shares of {} at {} target {} stop {}".format(
                                        env,
                                        shares_to_buy,
                                        symbol,
                                        data.close,
                                        target_prices[symbol],
                                        stop_price,
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
                                        side="buy",
                                        type="limit",
                                        time_in_force="day",
                                        limit_price=str(data.close),
                                    )
                                    open_orders[symbol] = o
                                    latest_cost_basis[symbol] = data.close
                                    return
                                    pass
                                except Exception:
                                    error_logger.report_exception()
                    else:
                        logger.log_text(
                            f"[{env}] failed MACD(40,60) for {symbol}!"
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
            macd_val = macd[-1]
            macd_signal_val = macd_signal[-1].round(2)

            macd_below_signal = macd_val < macd_signal_val
            bail_out = movement > 0.02 and macd_below_signal
            scalp = movement > 0.02
            below_cost_base = data.close <= latest_cost_basis[symbol]

            to_sell = False
            partial_sell = False
            sell_reasons = []
            if data.close <= stop_prices[symbol]:
                to_sell = True
                sell_reasons.append(f"stopped")
            elif below_cost_base and macd_val <= 0:
                to_sell = True
                sell_reasons.append(f"below cost & macd negative")
            elif data.close >= target_prices[symbol] and macd[-1] <= 0:
                to_sell = True
                sell_reasons.append(f"above target & macd negative")
            elif rsi[-1] >= 78:
                to_sell = True
                sell_reasons.append(f"rsi max")
            elif bail_out:
                to_sell = True
                sell_reasons.append(f"bail")
            elif scalp:
                partial_sell = True
                to_sell = True
                sell_reasons.append(f"scale-out")

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

                    if not partial_sell:
                        logger.log_text(
                            "[{}] Submitting sell for {} shares of {} at market".format(
                                env, symbol_position, symbol
                            )
                        )
                        o = api.submit_order(
                            symbol=symbol,
                            qty=str(symbol_position),
                            side="sell",
                            type="market",
                            time_in_force="day",
                        )
                    else:
                        qty = int(symbol_position / 3)
                        logger.log_text(
                            "[{}] Submitting sell for {} shares of {} at limit of {}".format(
                                env, str(qty), symbol, data.close
                            )
                        )
                        o = api.submit_order(
                            symbol=symbol,
                            qty=str(qty),
                            side="sell",
                            type="limit",
                            time_in_force="day",
                            limit_price=str(data.close),
                        )

                    open_orders[symbol] = o
                    latest_cost_basis[symbol] = data.close
                    return
                except Exception:
                    error_logger.report_exception()

        if until_market_close.seconds // 60 <= 15:
            logger.log_text(
                f"[{env}] {until_market_close.seconds // 60} minutes to market close for {symbol}"
            )
            if symbol_position:
                logger.log_text(
                    "[{}] Trading over, trying to liquidating remaining position in {}".format(
                        env, symbol
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
                        side="sell",
                        type="market",
                        time_in_force="day",
                    )
                    open_orders[symbol] = o
                    latest_cost_basis[symbol] = data.close
                except Exception:
                    error_logger.report_exception()
                return

            logger.log_text(f"[{env}] unsubscribe channels for {symbol}")
            try:
                if symbol in symbol:
                    symbols.remove(symbol)
                await conn.unsubscribe([f"A.{symbol}", f"AM.{symbol}"])
                logger.log_text(f"[{env}] {len(symbols)} channels left")
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
    """Handle failed websocket connections by reconnecting"""
    logger.log_text(f"[{env}] starting web-socket loop")

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
    logger.log_text(f"[{env}] save_start task starting")
    global run_details
    run_details = AlgoRun(name, environment, build, parameters)
    await set_db_connection(str(dsn))
    global db_conn_pool
    await run_details.save(pool=db_conn_pool)
    logger.log_text(f"[{env}] save_start task ended")


async def teardown_task(tz: DstTzInfo, market_close: datetime):
    global conn

    dt = datetime.today().astimezone(tz)
    to_market_close = market_close - dt

    logger.log_text(
        f"[{env}] tear-down task waiting for market close: {to_market_close}"
    )
    print(f"tear down waiting for market close: {to_market_close}")

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 10)
    except asyncio.CancelledError:
        print("teardown_task() cancelled during sleep")
        logger.log_text("teardown_task() cancelled during sleep")
    else:
        logger.log_text("tear down task starting")
        print("tear down task starting")
        await end_time("market close")
        asyncio.get_running_loop().stop()
    finally:
        logger.log_text(f"[{env}]tear down task done.")
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
        # _task_1 = asyncio.ensure_future(
        #    harvest_task(
        #        api,
        #        nyc,
        #        market_open + timedelta(minutes=15),
        #        market_open + timedelta(minutes=90),
        #    )
        # )
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
            get_tickers(prod_api),
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
