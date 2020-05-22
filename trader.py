"""
Trading strategy runner
"""
import multiprocessing as mp
import os
import sys
import time
from datetime import datetime

import alpaca_trade_api as tradeapi
import pygit2
from google.cloud import error_reporting
from pytz import timezone

from common import config, trading_data
from common.market_data import (get_historical_data, get_tickers, prev_closes,
                                volume_today)
from common.tlog import tlog
from consumer import consumer_main
from producer import producer_main

error_logger = error_reporting.Client()


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
                tlog(f"waiting for market open: {to_market_open}")
                if to_market_open.total_seconds() > 0:
                    try:
                        time.sleep(to_market_open.total_seconds() + 1)
                    except KeyboardInterrupt:
                        return False
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
    return True


"""
starting
"""


if __name__ == "__main__":
    trading_data.build_label = pygit2.Repository("./").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
    trading_data.filename = os.path.basename(__file__)
    motd(filename=trading_data.filename, version=trading_data.build_label)

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
            prev_closes[symbol] = ticker.prevDay["c"]
            volume_today[symbol] = ticker.day["v"]
        _symbols = [ticker.ticker for ticker in tickers]
        tlog(f"Tracking {len(_symbols)} symbols")

        minute_history = get_historical_data(
            api=data_api,
            symbols=_symbols,
            max_tickers=min(config.total_tickers, len(_symbols)),
        )

        queue: mp.Queue = mp.Queue()
        producer_process = mp.Process(
            target=producer_main, args=(queue, list(minute_history.keys())),
        )
        consumer_process = mp.Process(
            target=consumer_main, args=(queue, list(minute_history.keys()))
        )
        producer_process.start()
        consumer_process.start()
        producer_process.join()
        consumer_process.join()

        tlog("main completed")
        sys.exit(0)
