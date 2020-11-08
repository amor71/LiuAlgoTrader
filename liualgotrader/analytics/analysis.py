import asyncio
from datetime import date, timedelta
from typing import Dict, Tuple

import pandas as pd
from pytz import timezone

from liualgotrader.common.database import fetch_as_dataframe
from liualgotrader.common.tlog import tlog

est = timezone("America/New_York")


def portfolio_return(
    env: str, start_date: date
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_trades_for_period(env, start_date, date.today())

    # day X strategy = total return
    table: Dict = {}
    invested_table: Dict = {}
    percentages_table: Dict = {}
    for index, row in df.iterrows():
        d = pd.Timestamp(pd.to_datetime(row["client_time"]).date(), tz=est)
        if d not in table:
            table[d] = {}
            invested_table[d] = {}
            percentages_table[d] = {}
            table[d]["revenue"] = 0.0
            invested_table[d]["invested"] = 0.0

        strat = row["algo_name"]
        if not strat in table[d]:
            table[d][strat] = 0.0
            invested_table[d][strat] = 0.0
            percentages_table[d][strat] = 0.0
        delta = (
            (1.0 if row["operation"] == "sell" and row["qty"] > 0 else -1.0)
            * float(row["price"])
            * row["qty"]
        )
        table[d][strat] += delta
        table[d]["revenue"] += delta
        if row["operation"] == "buy":
            invested_table[d][strat] += row["qty"] * float(row["price"])
            invested_table[d]["invested"] += row["qty"] * float(row["price"])
        percentages_table[d][strat] = (
            (100.0 * table[d][strat] / invested_table[d][strat])
            if invested_table[d][strat] != 0
            else 0.0
        )
        percentages_table[d]["revenue"] = (
            (100.0 * table[d]["revenue"] / invested_table[d]["invested"])
            if invested_table[d][strat] != 0
            else 0.0
        )

    return (
        pd.DataFrame.from_dict(table, orient="index").sort_index(),
        pd.DataFrame.from_dict(invested_table, orient="index").sort_index(),
        pd.DataFrame.from_dict(percentages_table, orient="index").sort_index(),
    )


def load_trades_for_period(
    env: str, from_date: date, to_date: date
) -> pd.DataFrame:
    query = f"""
    SELECT client_time, symbol, operation, qty, price, algo_name
    FROM 
        new_trades as t, algo_run as a
    WHERE 
        t.algo_run_id = a.algo_run_id AND 
        t.tstamp >= '{from_date}' AND 
        t.tstamp < '{to_date}' AND
        t.expire_tstamp is null AND
        a.algo_env = '{env}'
    ORDER BY symbol, tstamp
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_as_dataframe(query))


def load_trades(day: date, env: str, end_date: date = None) -> pd.DataFrame:
    query = f"""
    SELECT t.*, a.batch_id, a.algo_name
    FROM 
    new_trades as t, algo_run as a
    WHERE 
        t.algo_run_id = a.algo_run_id AND 
        t.tstamp >= '{day}' AND 
        t.tstamp < '{day + timedelta(days=1) if not end_date else end_date}' AND
        t.expire_tstamp is null AND
        a.algo_env = '{env}'
    ORDER BY symbol, tstamp
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_as_dataframe(query))


def load_trades_by_batch_id(batch_id: str) -> pd.DataFrame:
    query = f"""
        SELECT 
            t.*, a.batch_id, a.start_time, a.algo_name
        FROM 
            new_trades as t, algo_run as a
        WHERE 
            t.algo_run_id = a.algo_run_id AND 
            a.batch_id = '{batch_id}' AND
            t.expire_tstamp is null 
        ORDER BY symbol, tstamp
    """
    loop = asyncio.get_event_loop()
    df: pd.DataFrame = loop.run_until_complete(fetch_as_dataframe(query))
    try:
        df["client_time"] = pd.to_datetime(df["client_time"])
    except Exception:
        tlog(
            f"[Error] load_trades_by_batch_id({batch_id}) can't convert 'client_time' column to datetime"
        )
    return df


def load_runs(day: date, env: str, end_date: date = None) -> pd.DataFrame:
    query = f"""
     SELECT * 
     FROM 
     algo_run as t
     WHERE 
         start_time >= '{day}' AND 
         start_time < '{day + timedelta(days=1) if not end_date else end_date}' AND
         algo_env = '{env}'
     ORDER BY start_time
     """
    loop = asyncio.get_event_loop()
    df = loop.run_until_complete(fetch_as_dataframe(query))
    df.set_index("algo_run_id", inplace=True)
    return df


def load_batch_list(day: date, env: str) -> pd.DataFrame:
    query = f"""
        SELECT DISTINCT a.batch_id, a.start_time
        FROM 
        new_trades as t, algo_run as a
        WHERE 
            t.algo_run_id = a.algo_run_id AND 
            t.tstamp >= '{day}' AND 
            t.tstamp < '{day + timedelta(days=1)}'AND
            t.expire_tstamp is null AND
            a.algo_env = '{env}'
        """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_as_dataframe(query))


def load_traded_symbols(batch_id: str) -> pd.DataFrame:
    query = f"""
        SELECT 
            DISTINCT t.symbol
        FROM 
            new_trades as t, algo_run as a
        WHERE 
            t.algo_run_id = a.algo_run_id AND 
            a.batch_id = '{batch_id}'
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_as_dataframe(query))


def load_batch_symbols(batch_id: str) -> pd.DataFrame:
    query = f"""
        SELECT 
            symbol
        FROM 
            trending_tickers
        WHERE 
            batch_id = '{batch_id}'
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_as_dataframe(query))


def calc_batch_revenue(
    symbol: str, trades: pd.DataFrame, batch_id: str = None
) -> float:
    symbol_df = trades[
        (trades["symbol"] == symbol)
        & (not batch_id or trades["batch_id"] == batch_id)
    ]
    rc = 0
    for index, row in symbol_df.iterrows():
        rc += (
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )
    return round(rc, 2)


def calc_revenue(symbol: str, trades: pd.DataFrame, env) -> float:
    symbol_df = trades[
        (trades["symbol"] == symbol) & (trades["algo_env"] == env)
    ]
    rc = 0
    for index, row in symbol_df.iterrows():
        rc += (
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )
    return round(rc, 2)


def count_trades(symbol, trades: pd.DataFrame, batch_id: str) -> int:
    symbol_df = trades[
        (trades["symbol"] == symbol) & (trades["batch_id"] == batch_id)
    ]
    return len(symbol_df.index)
