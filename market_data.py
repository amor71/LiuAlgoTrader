import time
from datetime import date, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import requests
from google.cloud import error_reporting
from google.cloud.logging import logger

import config

error_logger = error_reporting.Client()


def get_historical_data(
    my_logger: logger.Logger,
    env: str,
    strategy_name: str,
    api: tradeapi,
    symbols: List[str],
) -> Dict[str, object]:
    """get ticker history"""

    minute_history: Dict[str, object] = {}
    my_logger.log_text(f"[{env}][{strategy_name}]")
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
            my_logger.log_text(
                f"[{env}][{strategy_name}] {symbol} {c}/{len(symbols)}"
            )

    for x in exclude_symbols:
        symbols.remove(x)

    return minute_history


def get_tickers(
    my_logger: logger.Logger, env: str, strategy_name: str, api: tradeapi
) -> List[str]:
    """get all tickers"""

    my_logger.log_text(
        f"[{env}][{strategy_name}] Getting current ticker data..."
    )
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
                and config.max_share_price
                >= ticker.lastTrade["p"]
                >= config.min_share_price
                and ticker.prevDay["v"] * ticker.lastTrade["p"]
                > config.min_last_dv
                and ticker.todaysChangePerc >= config.today_change_percent
            )
        ]
        if len(rc) > 0:
            my_logger.log_text(
                f"[{env}][{strategy_name}] loaded {len(rc)} tickers"
            )
            return rc

        my_logger.log_text(
            f"[{env}][{strategy_name}] got no data :-( waiting then re-trying"
        )
        print("no tickers :-( waiting and retrying")
        time.sleep(30)
        max_retries -= 1

    my_logger.log_text(f"[{env}][{strategy_name}] got no data :-( giving up")
    return []
