import io
import time
from datetime import date, datetime, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import pandas as pd
import requests
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.fincalcs.vwap import add_daily_vwap

volume_today: Dict[str, int] = {}
quotes: Dict[str, df] = {}

m_and_a_data = pd.read_csv(
    "https://raw.githubusercontent.com/amor71/LiuAlgoTrader/master/database/market_m_a_data.csv"
).set_index("date")


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

                    except Exception:
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
                except Exception:
                    retry -= 1

    except KeyboardInterrupt:
        tlog("KeyboardInterrupt")

    return _minute_history


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


async def sp500_historical_constituents(date):
    tlog(f"loading sp500 constituents for {date}")
    table = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )
    symbols = table[0].Symbol.to_list()
    changes = table[1]
    changes["date"] = changes.Date.apply(
        lambda x: datetime.strptime(x[0], "%B %d, %Y"), axis=1
    )
    changes = changes.loc[changes.date > date]
    added = changes.Added.dropna().Ticker.to_list()
    removed = changes.Removed.dropna().Ticker.to_list()
    return list(set(symbols) - set(added)) + removed


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
        raise ValueError(
            f"Cant load {symbol} details for {date.today()-timedelta(days=5)} till {date.today()}"
        )

    return vals[-1]
