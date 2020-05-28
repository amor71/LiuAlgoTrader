"""
Trading strategy runner
"""
import multiprocessing as mp
import os
import sys
import time
import uuid
from datetime import datetime
from typing import List

import alpaca_trade_api as tradeapi
import pygit2
from google.cloud import error_reporting
from pytz import timezone

from common import config, trading_data
from common.market_data import get_historical_data, get_tickers, volume_today
from common.tlog import tlog
from consumer import consumer_main
from polygon_producer import polygon_producer_main

error_logger = error_reporting.Client()


def motd(filename: str, version: str, unique_id: str) -> None:
    """Display welcome message"""

    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"{filename} {version} starting")
    tlog(f"unique id: {unique_id}")
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


"""
process main
"""


def ready_to_start(trading_api: tradeapi) -> bool:
    nyc = timezone("America/New_York")
    config.market_open, config.market_close = get_trading_windows(
        nyc, trading_api
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
                if to_market_open.total_seconds() > 0:
                    try:
                        tlog(f"waiting for market open: {to_market_open}")
                        time.sleep(to_market_open.total_seconds() + 1)
                    except KeyboardInterrupt:
                        return False

                since_market_open = (
                    datetime.today().astimezone(nyc) - config.market_open
                )
                if (
                    since_market_open.seconds // 60
                    < config.market_cool_down_minutes
                ):
                    tlog(
                        f"market open, wait {config.market_cool_down_minutes} minutes"
                    )
                    while (
                        since_market_open.seconds // 60
                        < config.market_cool_down_minutes
                    ):
                        time.sleep(1)
                        since_market_open = (
                            datetime.today().astimezone(nyc)
                            - config.market_open
                        )

            tlog("ready to start")
            return True

    return False


"""
starting
"""


if __name__ == "__main__":
    trading_data.build_label = pygit2.Repository("./").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
    trading_data.filename = os.path.basename(__file__)

    uid = str(uuid.uuid4())
    motd(
        filename=trading_data.filename,
        version=trading_data.build_label,
        unique_id=uid,
    )

    data_api = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )

    if ready_to_start(data_api):
        tickers = get_tickers(data_api=data_api)

        # Update initial state with information from tickers
        for ticker in tickers:
            symbol = ticker.ticker
            # prev_closes[symbol] = ticker.prevDay["c"]
            volume_today[symbol] = ticker.day["v"]
        symbols = [ticker.ticker for ticker in tickers]
        tlog(f"Tracking {len(symbols)} symbols")

        minute_history = get_historical_data(
            api=data_api,
            symbols=symbols,
            max_tickers=min(config.total_tickers, len(symbols)),
        )
        symbols = list(minute_history.keys())

        if len(symbols) > 0:
            mp.set_start_method("spawn")

            # Consumers first
            _num_consumer_processes = (
                int(len(symbols) / config.num_consumer_processes_ratio) + 1
            )
            queues: List[mp.Queue] = [
                mp.Queue() for i in range(_num_consumer_processes)
            ]

            q_id_hash = {}
            for symbol in symbols:
                q_id_hash[symbol] = int(
                    list(minute_history.keys()).index(symbol)
                    / config.num_consumer_processes_ratio
                )
            consumers = [
                mp.Process(
                    target=consumer_main,
                    args=(queues[i], minute_history, uid),
                )
                for i in range(_num_consumer_processes)
            ]
            for p in consumers:
                # p.daemon = True
                p.start()

            # Producers second
            polygon_producer = mp.Process(
                target=polygon_producer_main,
                args=(queues, symbols, q_id_hash),
            )
            polygon_producer.start()

            # wait for completion and hope everyone plays nicely
            try:
                polygon_producer.join()
                for p in consumers:
                    p.join()
            except KeyboardInterrupt:
                polygon_producer.terminate()
                for p in consumers:
                    p.terminate()

    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"run {uid} completed")
    sys.exit(0)
