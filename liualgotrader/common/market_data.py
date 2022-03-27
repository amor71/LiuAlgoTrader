from datetime import date, datetime
from typing import Dict, List, Set

import numpy as np
import pandas as pd
import pandas_market_calendars
import pytz
import requests
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.data_loader import m_and_a_data  # type: ignore
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.fincalcs.vwap import add_daily_vwap

volume_today: Dict[str, int] = {}
quotes: Dict[str, df] = {}

NY = "America/New_York"
nytz = pytz.timezone(NY)


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


async def sp500_historical_constituents(date: str):
    tlog(f"loading sp500 constituents for {date}")
    table = pd.read_html(
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    )
    symbols: List = table[0].Symbol.to_list()
    changes = table[1]

    changes["date"] = changes.Date.apply(
        lambda x: datetime.strptime(x[0], "%B %d, %Y"), axis=1
    )
    m_and_a_data.index = m_and_a_data.index.astype("datetime64[ns]", copy=True)

    adjusted_symbols = m_and_a_data.loc[date < m_and_a_data.index, "to_symbol"]
    print("adjusted_symbols", adjusted_symbols)
    changes = changes.loc[changes.date > date]

    unadusted: Set = set(symbols)
    while True:
        no_changes = True
        for _, row in changes.iterrows():
            if not row.Added.dropna().empty and row.Added.Ticker in unadusted:
                unadusted.remove(row.Added.Ticker)
                no_changes = False
            if (
                not row.Removed.dropna().empty
                and row.Removed.Ticker in unadusted
            ):
                unadusted.add(row.Removed.Ticker)
                no_changes = False

        if no_changes:
            break

    while True:
        no_changes = True
        for symbol in adjusted_symbols:
            if symbol in unadusted:
                unadusted.add(
                    m_and_a_data.loc[
                        m_and_a_data.to_symbol == symbol, "from_symbol"
                    ].item()
                )
                unadusted.remove(symbol)
                no_changes = False

        if no_changes:
            break

    return list(unadusted)


async def get_trading_holidays() -> List[str]:
    nyse = pandas_market_calendars.get_calendar("NYSE")
    return nyse.holidays().holidays


async def get_trading_day(now: date, offset: int) -> date:
    cbd_offset = pd.tseries.offsets.CustomBusinessDay(
        n=-offset, holidays=await get_trading_holidays()
    )

    return (now + cbd_offset).date()
