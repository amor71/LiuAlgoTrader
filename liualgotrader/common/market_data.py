import io
import time
from datetime import date, datetime, timedelta
from typing import Dict, List

import pandas as pd
import pandas_market_calendars
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


async def get_trading_holidays() -> List[str]:
    nyse = pandas_market_calendars.get_calendar("NYSE")
    return nyse.holidays().holidays


async def get_trading_day(now: date, offset: int) -> date:
    cbd_offset = pd.tseries.offsets.CustomBusinessDay(
        n=-offset, holidays=await get_trading_holidays()
    )

    return (now + cbd_offset).date()
