"""
Momentum Trading Algorithm
"""
import os
import time
from datetime import datetime, timedelta

import alpaca_trade_api as tradeapi
import git
import numpy as np
import requests
from google.cloud import error_reporting, logging
from pytz import timezone
from talib import MACD, RSI

client = logging.Client()
logger = client.logger("algo")
error_logger = error_reporting.Client()

# Replace these with your API connection info from the dashboard
paper_base_url = "https://paper-api.alpaca.markets"
paper_api_key_id = "PK9C21VXOA9CAIXNJ355"
paper_api_secret = "nq/ZP/YOCod8La/fZVMT7zLpMrTcWnnFCx4ewO0p"

prod_base_url = "https://api.alpaca.markets"
prod_api_key_id = "AKVKN4TLUUS5MZO5KYLM"
prod_api_secret = "nkK2UmvE1kTFFw1ZlaqDmwCyiuCu7OOeB5y2La/X"

session = requests.session()

# We only consider stocks with per-share prices inside this range
min_share_price = 2.0
max_share_price = 20.0
# Minimum previous-day dollar volume for a stock we might consider
min_last_dv = 500000
# Stop limit to default to
default_stop = 0.95
# How much of our portfolio to allocate to any one position
risk = 0.001


def get_1000m_history_data(api, symbols):
    """get ticker history"""
    logger.log_text("Getting historical data...")
    minute_history = {}
    c = 0
    for symbol in symbols:
        minute_history[symbol] = api.polygon.historic_agg(
            size="minute", symbol=symbol, limit=1000
        ).df
        c += 1
        logger.log_text(f"{symbol} {c}/{len(symbols)}")
    logger.log_text("Success.")
    return minute_history


def get_tickers(api):
    """get all tickets"""
    logger.log_text("Getting current ticker data...")
    tickers = api.polygon.all_tickers()
    logger.log_text("Success.")
    assets = api.list_assets()
    symbols = [asset.symbol for asset in assets if asset.tradable]
    return [
        ticker
        for ticker in tickers
        if (
            ticker.ticker in symbols
            and max_share_price >= ticker.lastTrade["p"] >= min_share_price
            and ticker.prevDay["v"] * ticker.lastTrade["p"] > min_last_dv
            and ticker.todaysChangePerc >= 3.5
        )
    ]


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
    base_url,
    api_key_id,
    api_secret,
    trade_buy_window,
):
    """main loop"""
    # Establish streaming connection
    conn = tradeapi.StreamConn(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret
    )

    # Update initial state with information from tickers
    volume_today = {}
    prev_closes = {}
    for ticker in tickers:
        symbol = ticker.ticker
        prev_closes[symbol] = ticker.prevDay["c"]
        volume_today[symbol] = ticker.day["v"]

    symbols = [ticker.ticker for ticker in tickers]
    logger.log_text("Tracking {} symbols.".format(len(symbols)))
    minute_history = get_1000m_history_data(api, symbols)

    portfolio_value = float(api.get_account().portfolio_value)

    open_orders = {}
    positions = {}

    # Cancel any existing open orders on watched symbols
    existing_orders = api.list_orders(limit=500)
    for order in existing_orders:
        if order.symbol in symbols:
            logger.log_text(f"cancel open order of {order.symbol}")
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

    channels = ["trade_updates"]
    for symbol in symbols:
        symbol_channels = ["A.{}".format(symbol), "AM.{}".format(symbol)]
        channels += symbol_channels
    logger.log_text("Watching {} symbols.".format(len(symbols)))

    # Use trade updates to keep track of our portfolio
    @conn.on(r"trade_update")
    async def handle_trade_update(conn, channel, data):
        symbol = data.order["symbol"]
        last_order = open_orders.get(symbol)
        if last_order is not None:
            logger.log_text(f"trade update for {symbol}")
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
                open_orders[symbol] = data.order
            elif event == "fill":
                qty = int(data.order["filled_qty"])
                if data.order["side"] == "sell":
                    qty = qty * -1
                positions[symbol] = positions.get(
                    symbol, 0
                ) - partial_fills.get(symbol, 0)
                partial_fills[symbol] = 0
                positions[symbol] += qty
                open_orders[symbol] = None
            elif event in ("canceled", "rejected"):
                partial_fills[symbol] = 0
                open_orders[symbol] = None

    @conn.on(r"A$")
    async def handle_second_bar(conn, channel, data):
        symbol = data.symbol

        # First, aggregate 1s bars for up-to-date MACD calculations
        ts = data.start
        ts -= timedelta(seconds=ts.second, microseconds=ts.microsecond)
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
                order_lifetime = ts - submission_ts
                if order_lifetime.seconds // 60 > 1:
                    # Cancel it so we can try again for a fill
                    logger.log_text(
                        f"Cancel order id {existing_order.id} for {symbol}"
                    )
                    api.cancel_order(existing_order.id)
                return
            except AttributeError:
                error_logger.report_exception()
                logger.log_text(
                    f"Attribute Error in symbol {symbol} w/ {existing_order}"
                )

        # Now we check to see if it might be time to buy or sell
        since_market_open = ts - market_open_dt
        until_market_close = market_close_dt - ts

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
                    f"{symbol} high_15m={high_15m} data.close={data.close}"
                )
                # check for a positive, increasing MACD
                macd1 = MACD(minute_history[symbol]["close"].dropna())[0]
                if (
                    macd1[-1] > 0
                    and macd1[-4] <= macd1[-3] < macd1[-2] < macd1[-1]
                ):
                    logger.log_text(f"MACD(12,26) for {symbol} trending up!")
                    macd2 = MACD(
                        minute_history[symbol]["close"].dropna(), 40, 60
                    )[0]
                    if macd2[-1] > 0 and np.diff(macd2)[-1] > 0:
                        logger.log_text(
                            f"MACD(40,60) for {symbol} trending up!"
                        )

                        # check RSI does not indicate overbought
                        rsi = RSI(minute_history[symbol]["close"].dropna(), 14)

                        if rsi[-1] < 60:
                            logger.log_text(f"RSI {rsi[-1]} < 60")
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
                                    "Submitting buy for {} shares of {} at {} target {} stop {}".format(
                                        shares_to_buy,
                                        symbol,
                                        data.close,
                                        target_prices[symbol],
                                        stop_price,
                                    )
                                )
                                try:
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

        if (
            since_market_open.seconds // 60 >= 24
            and until_market_close.seconds // 60 > 15
            and symbol_position > 0
        ):
            # Check for liquidation signals

            # Sell for a loss if it's fallen below our stop price
            # Sell for a loss if it's below our cost basis and MACD < 0
            # Sell for a profit if it's above our target price
            macd = MACD(minute_history[symbol]["close"].dropna(), 13, 21)[0]
            rsi = RSI(minute_history[symbol]["close"].dropna(), 14)
            if (
                data.close <= stop_prices[symbol]
                or macd[-1] <= 0
                or data.close >= target_prices[symbol]
                or rsi[-1] >= 77
            ):
                #                data.close <= stop_prices[symbol]
                #                or (data.close >= target_prices[symbol] and macd[-1] <= 0)
                #                or (data.close <= latest_cost_basis[symbol] and macd[-1] <= 0)
                logger.log_text(
                    "Submitting sell for {} shares of {} at {}".format(
                        symbol_position, symbol, data.close
                    )
                )
                try:
                    o = api.submit_order(
                        symbol=symbol,
                        qty=str(symbol_position),
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
                f"{until_market_close.seconds // 60} minutes to market close for {symbol}"
            )
            if symbol_position:
                logger.log_text(
                    "Trading over, trying to liquidating remaining position in {}".format(
                        symbol
                    )
                )
                try:
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

            logger.log_text(f"unsubscribe channels for {symbol}")
            try:
                symbols.remove(symbol)
                await conn.unsubscribe([f"A.{symbol}", f"AM.{symbol}"])
                logger.log_text(f"{len(symbols)} channels left")

                if len(symbols) <= 0:
                    logger.log_text("last channel! closing connection")
                    await conn.close()
            except Exception:
                error_logger.report_exception()

    # Replace aggregated 1s bars with incoming 1m bars
    @conn.on(r"AM$")
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

    if len(symbols) > 0:
        run_ws(base_url, api_key_id, api_secret, conn, channels)


def run_ws(base_url, api_key_id, api_secret, conn, channels):
    """Handle failed websocket connections by reconnecting"""
    logger.log_text("starting webscoket loop")

    try:
        conn.run(channels)
    except Exception as e:
        print(str(e))
        error_logger.report_exception()

        # re-establish streaming connection
        conn = tradeapi.StreamConn(
            base_url=base_url, key_id=api_key_id, secret_key=api_secret
        )
        run_ws(base_url, api_key_id, api_secret, conn, channels)


if __name__ == "__main__":
    r = git.repo.Repo("./")
    label = r.git.describe()
    fname = os.path.basename(__file__)
    msg = f"{fname} {label} starting!"
    logger.log_text(msg)
    print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
    print(msg)
    print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")
    env = os.getenv("TRADE", "PAPER")
    trade_buy_window = int(os.getenv("TRADE_BUY_WINDOW", "120"))
    base_url = prod_base_url if env == "PROD" else paper_base_url
    api_key_id = prod_api_key_id if env == "PROD" else paper_api_key_id
    api_secret = prod_api_secret if env == "PROD" else paper_api_secret
    api = tradeapi.REST(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret
    )
    print(f"TRADE environment {env}")
    print(f"TRADE_BUY_WINDOW {trade_buy_window}")
    print(f"base_url: {base_url}")
    print("-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-")

    # Get when the market opens or opened today
    nyc = timezone("America/New_York")
    today = datetime.today().astimezone(nyc)
    today_str = datetime.today().astimezone(nyc).strftime("%Y-%m-%d")
    calendar = api.get_calendar(start=today_str, end=today_str)[0]
    market_open = today.replace(
        hour=calendar.open.hour, minute=calendar.open.minute, second=0
    )
    logger.log_text(f"markets open {market_open}")
    print(f"markets open {market_open}")
    market_open = market_open.astimezone(nyc)
    market_close = today.replace(
        hour=calendar.close.hour, minute=calendar.close.minute, second=0
    )
    market_close = market_close.astimezone(nyc)
    logger.log_text(f"markets close {market_close}")
    print(f"markets close {market_close}")

    # Wait until just before we might want to trade
    current_dt = datetime.today().astimezone(nyc)
    logger.log_text(f"current time {current_dt}")

    if current_dt < market_close:
        to_market_open = market_open - current_dt
        logger.log_text(f"waiting for market open: {to_market_open}")
        print(f"waiting for market open: {to_market_open}")

        if to_market_open.total_seconds() > 0:
            time.sleep(to_market_open.total_seconds() + 1)

        logger.log_text(f"market open! wait ~14 minutes")
        since_market_open = datetime.today().astimezone(nyc) - market_open
        while since_market_open.seconds // 60 <= 14:
            time.sleep(1)
            since_market_open = datetime.today().astimezone(nyc) - market_open

        logger.log_text("ready to start!")
        print("ready to start!")
        run(
            get_tickers(api),
            market_open,
            market_close,
            api,
            base_url,
            api_key_id,
            api_secret,
            trade_buy_window,
        )
    else:
        logger.log_text(
            "OH, missed the entry time, try again next trading day"
        )
        print("OH, missed the entry time, try again next trading day")

    logger.log_text("Done.")
    print("Done.")
