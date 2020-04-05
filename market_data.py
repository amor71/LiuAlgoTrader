import time
from datetime import date, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import requests
from alpaca_trade_api.polygon.entity import Ticker
from google.cloud import error_reporting
from pandas import DataFrame as df

import config
from tlog import tlog

error_logger = error_reporting.Client()

prev_closes: Dict[str, float] = {}
volume_today: Dict[str, int] = {}


def get_historical_data(api: tradeapi, symbols: List[str],) -> Dict[str, df]:
    """get ticker history"""

    minute_history: Dict[str, object] = {}
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
            tlog(f"loaded agg data for {symbol} {c}/{len(symbols)}")

    for x in exclude_symbols:
        symbols.remove(x)

    return minute_history


async def get_tickers(data_api: tradeapi) -> List[Ticker]:
    """get all tickers"""

    tlog("Getting current ticker data...")
    max_retries = 50
    while max_retries > 0:
        tickers = data_api.polygon.all_tickers()
        assets = data_api.list_assets()
        tradable_symbols = [asset.symbol for asset in assets if asset.tradable]
        rc = [
            ticker
            for ticker in tickers
            if (
                ticker.ticker in tradable_symbols
                and config.max_share_price
                >= ticker.lastTrade["p"]
                >= config.min_share_price
                and ticker.prevDay["v"] * ticker.lastTrade["p"]
                > config.min_last_dv
                and ticker.todaysChangePerc >= config.today_change_percent
            )
        ]
        if len(rc) > 0:
            tlog(f"loaded {len(rc)} tickers")
            return rc

        tlog("got no data :-( waiting then re-trying")
        time.sleep(30)
        max_retries -= 1

    tlog("got no data :-( giving up")
    return []
