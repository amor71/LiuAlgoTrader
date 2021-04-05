import asyncio
import json
from datetime import date, timedelta
from typing import Dict, Tuple

import pandas as pd
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.database import fetch_as_dataframe
from liualgotrader.common.tlog import tlog

est = timezone("America/New_York")


def portfolio_return(
    env: str, start_date: date
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df = load_trades_for_period(
        env, start_date, date.today() + timedelta(days=1)
    )

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
        if strat not in table[d]:
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


def load_trades(day: date, end_date: date = None) -> pd.DataFrame:
    query = f"""
    SELECT t.*, a.batch_id, a.algo_name
    FROM 
    new_trades as t, algo_run as a
    WHERE 
        t.algo_run_id = a.algo_run_id AND 
        t.tstamp >= '{day}' AND 
        t.tstamp < '{day + timedelta(days=1) if not end_date else end_date}' AND
        t.expire_tstamp is null 
    ORDER BY symbol, tstamp
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(fetch_as_dataframe(query))


async def aload_trades_by_batch_id(batch_id: str) -> pd.DataFrame:
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
    df: pd.DataFrame = await fetch_as_dataframe(query)
    try:
        if not df.empty:
            df["client_time"] = pd.to_datetime(df["client_time"])
    except Exception:
        tlog(
            f"[Error] aload_trades_by_batch_id({batch_id}) can't convert 'client_time' column to datetime"
        )
    return df


def load_trades_by_batch_id(batch_id: str) -> pd.DataFrame:
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(aload_trades_by_batch_id(batch_id))


def load_runs(day: date, end_date: date = None) -> pd.DataFrame:
    query = f"""
     SELECT * 
     FROM 
     algo_run as t
     WHERE 
         start_time >= '{day}' AND 
         start_time < '{day + timedelta(days=1) if not end_date else end_date}'
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
            t.expire_tstamp is null 
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
    rc = sum(
        (
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )
        for index, row in symbol_df.iterrows()
    )
    return round(rc, 2)


def calc_revenue(symbol: str, trades: pd.DataFrame, env) -> float:
    symbol_df = trades[
        (trades["symbol"] == symbol) & (trades["algo_env"] == env)
    ]
    rc = sum(
        (
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )
        for index, row in symbol_df.iterrows()
    )
    return round(rc, 2)


def count_trades(symbol, trades: pd.DataFrame, batch_id: str) -> int:
    symbol_df = trades[
        (trades["symbol"] == symbol) & (trades["batch_id"] == batch_id)
    ]
    return len(symbol_df.index)


def trades_analysis(trades: pd.DataFrame, batch_id: str) -> pd.DataFrame:
    day_to_analyze = min(trades["client_time"].tolist())
    config.market_open = day_to_analyze.replace(
        hour=9, minute=30, second=0, microsecond=0
    )
    trades_anlytics = pd.DataFrame()
    trades["client_time"] = pd.to_datetime(trades["client_time"], utc=True)
    trades_anlytics["symbol"] = trades.symbol.unique()
    trades_anlytics["revenues"] = trades_anlytics["symbol"].apply(
        lambda x: calc_batch_revenue(x, trades, batch_id)
    )
    trades_anlytics["count"] = trades_anlytics["symbol"].apply(
        lambda x: count_trades(x, trades, batch_id)
    )

    return trades_anlytics


def symobl_trade_analytics(
    symbol_df: pd.DataFrame, open_price: float, plt
) -> Tuple[pd.DataFrame, float]:
    delta = 0.0
    profit = 0.0

    operations = []
    deltas = []
    profits = []
    times = []
    prices = []
    qtys = []
    indicators = []
    target_price = []
    stop_price = []
    daily_change = []
    precent_vwap = []
    algo_names = []
    for _, row in symbol_df.iterrows():
        delta = (
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )
        profit += float(delta)
        plt.scatter(
            row["client_time"].to_pydatetime(),
            row["price"],
            c="g" if row["operation"] == "buy" else "r",
            s=100,
        )
        algo_names.append(row["algo_name"])
        deltas.append(round(delta, 2))
        profits.append(round(profit, 2))
        operations.append(row["operation"])
        times.append(pd.to_datetime(row["client_time"]))
        prices.append(row["price"])
        qtys.append(row["qty"])
        indicator = json.loads(row.indicators)
        indicators.append(indicator)
        target_price.append(row["target_price"])
        stop_price.append(row["stop_price"])
        daily_change.append(
            f"{round(100.0 * (float(row['price']) - open_price) / open_price, 2)}%"
        )
        precent_vwap.append(
            f"{round(100.0 * (indicator['buy']['avg'] - open_price) / open_price, 2)}%"
            if "buy" in indicator
            and indicator["buy"]
            and "avg" in indicator["buy"]
            else ""
        )

    d = {
        "balance": profits,
        "trade": deltas,
        "algo": algo_names,
        "operation": operations,
        "at": times,
        "price": prices,
        "qty": qtys,
        "daily change": daily_change,
        "vwap": precent_vwap,
        "indicators": indicators,
        "target price": target_price,
        "stop price": stop_price,
    }

    return pd.DataFrame(d), profit
