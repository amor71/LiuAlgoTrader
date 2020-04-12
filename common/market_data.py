import time
from datetime import date, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import requests
from alpaca_trade_api.common import get_polygon_credentials
from alpaca_trade_api.polygon.entity import Ticker
from asyncpg.pool import Pool
from google.cloud import error_reporting
from pandas import DataFrame as df

from common import config, trading_data
from common.tlog import tlog
from models.ticker_snapshot import TickerSnapshot

try:
    error_logger = error_reporting.Client()
except Exception:
    error_logger = None

prev_closes: Dict[str, float] = {}
volume_today: Dict[str, int] = {}


def get_historical_data(api: tradeapi, symbols: List[str],) -> Dict[str, df]:
    """get ticker history"""

    minute_history: Dict[str, df] = {}
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
                        if error_logger:
                            error_logger.report_exception()
                        exclude_symbols.append(symbol)
            c += 1
            tlog(
                f"loaded {len(minute_history[symbol].index)} agg data points for {symbol} {c}/{len(symbols)}"
            )

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


async def calculate_trends(pool: Pool) -> bool:
    # load snapshot
    with requests.Session() as session:
        url = (
            "https://api.polygon.io/"
            + "v2/snapshot/locale/us/markets/stocks/tickers"
        )
        with session.get(
            url,
            params={"apiKey": get_polygon_credentials(config.prod_api_key_id)},
        ) as response:
            if (
                response.status_code == 200
                and (r := response.json())["status"] == "OK"
            ):
                for ticker in r["tickers"]:
                    trading_data.snapshot[ticker.ticker] = TickerSnapshot(
                        symbol=ticker["ticker"],
                        volume=ticker["day"]["volume"],
                        today_change=ticker["todaysChangePerc"],
                    )
                    print(trading_data.snapshot[ticker.ticker])

                # load industry & sector mappings
                # sectors = await get_market_industries(pool)
                # industries = await get_market_industries(pool)

                # sector_mapping = {}

                # industry_mapping = {}
                # per each industry, calculate trend

                # per each sector, calculate trend

                return True

    return False


async def get_sector_tickers(pool: Pool, sector: str) -> List[str]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            records = await conn.fetch(
                """
                    SELECT symbol
                    FROM ticker_data
                    WHERE sector = $1
                """,
                sector,
            )

            return [record[0] for record in records if record[0]]


async def get_industry_tickers(pool: Pool, industry: str) -> List[str]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            records = await conn.fetch(
                """
                    SELECT symbol
                    FROM ticker_data
                    WHERE industry = $1
                """,
                industry,
            )

            return [record[0] for record in records if record[0]]


async def get_market_sectors(pool: Pool) -> List[str]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            records = await conn.fetch(
                """
                    SELECT DISTINCT sector
                    FROM ticker_data
                """
            )
            return [record[0] for record in records if record[0]]


async def get_market_industries(pool: Pool) -> List[str]:
    async with pool.acquire() as conn:
        async with conn.transaction():
            records = await conn.fetch(
                """
                    SELECT DISTINCT industry
                    FROM ticker_data
                """
            )

            return [record[0] for record in records if record[0]]
