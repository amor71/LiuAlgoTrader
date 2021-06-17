import io
import time
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import alpaca_trade_api as tradeapi
import pandas as pd
import requests
from alpaca_trade_api.common import get_polygon_credentials
from asyncpg.pool import Pool
from pandas import DataFrame as df
from pandas import Timestamp
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.fincalcs.vwap import add_daily_vwap
from liualgotrader.models.ticker_snapshot import TickerSnapshot

volume_today: Dict[str, int] = {}
quotes: Dict[str, df] = {}


def get_historical_data_from_finnhub(symbols: List[str]) -> Dict[str, df]:

    tlog(f"Loading {len(symbols)} tickers historic data from Finnhub")
    nyc = timezone(NY := "America/New_York")
    _from = datetime.today().astimezone(nyc) - timedelta(days=30)
    _from = _from.replace(hour=9, minute=29, second=0, microsecond=0)
    _to = datetime.now(nyc)

    minute_history: Dict[str, df] = {}
    with requests.Session() as s:
        try:
            c = 0
            for symbol in symbols:
                retry = True
                while retry:
                    retry = False

                    url = f"{config.finnhub_base_url}/stock/candle?symbol={symbol}&resolution=1&from={_from.strftime('%s')}&to={_to.strftime('%s')}&token={config.finnhub_api_key}"
                    r = s.get(url)

                    if r.status_code == 200:
                        response = r.json()
                        if response["s"] != "no_data":
                            _data = {
                                "close": response["c"],
                                "open": response["o"],
                                "high": response["h"],
                                "low": response["l"],
                                "volume": response["v"],
                            }

                            _df = df(
                                _data,
                                index=[
                                    Timestamp(item, tz=NY, unit="s")
                                    for item in response["t"]
                                ],
                            )
                            c += 1
                            _df["vwap"] = 0.0
                            _df["average"] = 0.0
                            minute_history[symbol] = _df
                            tlog(
                                f"loaded {len(minute_history[symbol].index)} agg data points for {symbol} ({c}/{len(symbols)})"
                            )
                    elif r.status_code == 429:
                        tlog(
                            f"{symbols.index(symbol)}/{len(symbols)} API limit: ({r.text})"
                        )
                        time.sleep(30)
                        retry = True
                    else:
                        tlog(f"[ERROR] {r.status_code}, {r.text}")

        except KeyboardInterrupt:
            tlog("KeyboardInterrupt")
            pass

    return minute_history


def get_historical_data_from_poylgon_for_symbols(
    api: tradeapi, symbols: List[str], start_date: date, end_date: date
) -> Dict[str, df]:
    minute_history = {}
    for symbol in symbols:
        if symbol not in minute_history:
            minute_history[symbol] = api.polygon.historic_agg_v2(
                symbol,
                1,
                "minute",
                _from=start_date,
                to=end_date,
            ).df.tz_convert("US/Eastern")
            add_daily_vwap(minute_history[symbol])

    return minute_history


def get_historical_data_from_polygon_by_range(
    api: tradeapi, symbols: List[str], start_date: date, timespan: str
) -> Dict[str, df]:
    """get ticker history"""

    _minute_history: Dict[str, df] = {}
    try:
        for symbol in symbols:
            from_date = start_date
            while from_date < date.today():
                retry = 5
                _df = None
                while retry > 0:
                    try:
                        _df = api.polygon.historic_agg_v2(
                            symbol,
                            1,
                            timespan,
                            _from=str(from_date),
                            to=str(
                                from_date
                                + timedelta(
                                    days=1 + config.polygon.MAX_DAYS_TO_LOAD
                                )
                            ),
                        ).df
                        break

                    except Exception as e:

                        retry -= 1

                if _df is None or not len(_df):
                    break

                _df["vwap"] = 0.0
                _df["average"] = 0.0

                _minute_history[symbol] = (
                    pd.concat([_minute_history[symbol], _df])
                    if symbol in _minute_history
                    else _df
                )

                from_date = _df.index[-1] + timedelta(days=1)

                tlog(
                    f"get_historical_data_from_polygon_by_range() - total loaded {len(_minute_history[symbol].index)} agg data points for {symbol}"
                )
    except KeyboardInterrupt:
        tlog("KeyboardInterrupt")

    return _minute_history


def get_symbol_data(
    symbol: str,
    start_date: date,
    end_date: date,
    data_loader=None,
    scale="minute",
) -> df:
    if not data_loader:
        data_loader = DataLoader(TimeScale[scale])

    return data_loader[symbol][start_date:end_date]  # type: ignore


def daily_bars(api: tradeapi, symbol: str, days: int) -> df:
    retry = 10

    while retry:
        try:
            _df = api.polygon.historic_agg_v2(
                symbol,
                1,
                "day",
                _from=str(date.today() - timedelta(days=days)),
                to=str(date.today()),
            ).df

            if _df.empty:
                tlog(
                    f"empty dataset received for {symbol} daily bars, resting and retrying."
                )
                time.sleep(30)
                retry -= 1
                continue

        except Exception as e:
            if retry:
                tlog(
                    f"[EXCEPTION] {e} during loading {symbol} daily bars, resting and retrying."
                )
                time.sleep(30)
                retry -= 1
            else:
                raise
        else:
            return _df

    raise Exception(f"Failed to load data for {symbol}")


def get_historical_daily_from_polygon_by_range(
    api: tradeapi, symbols: List[str], start_date: date, end_date: date
) -> Dict[str, df]:
    """get ticker history"""

    _minute_history: Dict[str, df] = {}
    try:
        for symbol in symbols:
            retry = 5
            _df = None
            while retry > 0:
                try:
                    _df = api.polygon.historic_agg_v2(
                        symbol,
                        1,
                        "day",
                        _from=str(start_date),
                        to=str(end_date),
                    ).df

                    _df["vwap"] = 0.0
                    _df["average"] = 0.0

                    _minute_history[symbol] = (
                        pd.concat([_minute_history[symbol], _df])
                        if symbol in _minute_history
                        else _df
                    )
                    break
                except Exception as e:
                    retry -= 1
                    continue

    except KeyboardInterrupt:
        tlog("KeyboardInterrupt")

    return _minute_history


def get_historical_data_from_polygon(
    api: tradeapi, symbols: List[str], max_tickers: int
) -> Dict[str, df]:
    """get ticker history"""

    tlog(f"Loading max {max_tickers} tickers w/ highest volume from Polygon")
    minute_history: Dict[str, df] = {}
    c = 0
    exclude_symbols = []
    try:
        for symbol in symbols:
            if symbol not in minute_history:
                retry_counter = 5
                while retry_counter > 0:
                    try:
                        if c < max_tickers:
                            _df = api.polygon.historic_agg_v2(
                                symbol,
                                1,
                                "minute",
                                _from=str(date.today() - timedelta(days=10)),
                                to=str(date.today() + timedelta(days=1)),
                            ).df
                            _df["vwap"] = 0.0
                            _df["average"] = 0.0

                            minute_history[symbol] = _df
                            tlog(
                                f"loaded {len(minute_history[symbol].index)} agg data points for {symbol} {c+1}/{max_tickers}"
                            )
                            c += 1
                            break

                        exclude_symbols.append(symbol)
                        break
                    except (
                        requests.exceptions.HTTPError,
                        requests.exceptions.ConnectionError,
                    ):
                        retry_counter -= 1
                        if retry_counter == 0:
                            exclude_symbols.append(symbol)
    except KeyboardInterrupt:
        tlog("KeyboardInterrupt")

    for x in exclude_symbols:
        symbols.remove(x)

    tlog(f"Total number of symbols for trading {len(symbols)}")
    return minute_history


async def get_sector_tickers(sector: str) -> List[str]:
    async with config.db_conn_pool.acquire() as conn:
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


async def get_sectors_tickers(sectors: List[str]) -> List[str]:
    async with config.db_conn_pool.acquire() as conn:
        async with conn.transaction():
            q = f"""
                    SELECT symbol
                    FROM ticker_data
                    WHERE sector in ({str(sectors)[1:-1]})
                """

            records = await conn.fetch(q)

    return [record[0] for record in records if record[0]]


async def get_industry_tickers(industry: str) -> List[str]:
    async with config.db_conn_pool.acquire() as conn:
        records = await conn.fetch(
            """
                SELECT symbol
                FROM ticker_data
                WHERE industry = $1
            """,
            industry,
        )

    return [record[0] for record in records if record[0]]


async def get_industries_tickers(industries: List[str]) -> List[str]:
    async with config.db_conn_pool.acquire() as conn:
        q = f"""
                SELECT symbol
                FROM ticker_data
                WHERE industry in ({str(industries)[1:-1]})
            """

        records = await conn.fetch(q)

    return [record[0] for record in records if record[0]]


async def get_market_sectors() -> List[str]:
    async with config.db_conn_pool.acquire() as conn:
        records = await conn.fetch(
            """
                SELECT DISTINCT sector
                FROM ticker_data
            """
        )
        return [record[0] for record in records if record[0]]


async def get_market_industries() -> List[str]:
    async with config.db_conn_pool.acquire() as conn:
        records = await conn.fetch(
            """
                SELECT DISTINCT industry
                FROM ticker_data
            """
        )

        return [record[0] for record in records if record[0]]


async def index_data(index: str) -> df:
    if index == "SP500":
        table = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )
        return table[0]
    raise NotImplementedError(f"index {index} not supported yet")


async def index_history(index: str, days: int) -> df:
    if index == "SP500":
        start = (
            date.today() - timedelta(days=int(days * 7 / 5) + 20)
        ).strftime("%s")
        end = date.today().strftime("%s")

        url = f"https://query1.finance.yahoo.com/v7/finance/download/%5EGSPC?period1={start}&period2={end}&interval=1d&events=history&includeAdjustedClose=true"
        s = requests.get(url).content
        return pd.read_csv(io.StringIO(s.decode("utf-8")))

    raise NotImplementedError(f"index {index} not supported yet")


def latest_stock_price(data_api: tradeapi, symbol: str) -> float:
    """Load latest stock price for symbol"""

    vals = data_api.polygon.historic_agg_v2(
        symbol,
        1,
        "minute",
        _from=str(date.today() - timedelta(days=5)),
        to=str(date.today()),
    ).df.close.tolist()

    if not len(vals):
        raise Exception(
            f"Cant load {symbol} details for {str(date.today()-timedelta(days=5))} till {str(date.today())}"
        )

    return vals[-1]
