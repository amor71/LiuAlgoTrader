import asyncio
import json
from datetime import date, timedelta
from typing import Dict

import matplotlib.pyplot as plt
import nest_asyncio
import pandas as pd
import pytz
import requests
import streamlit as st

from liualgotrader.analytics.analysis import (calc_batch_revenue, count_trades,
                                              load_runs, load_trades)
from liualgotrader.common import database
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import TimeScale

st.title("Day-trade Session Analysis")
st.markdown(
    "#### View and analyze the performance of your day-trading session."
)

day_to_analyze = st.date_input("pick day to analyze", value=date.today())
env = st.sidebar.selectbox("Select environment", ("PAPER", "BACKTEST", "PROD"))

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
nest_asyncio.apply()

loop.run_until_complete(database.create_db_connection())

with st.spinner(f"loading {day_to_analyze} data.."):
    # Create DB connection & load data
    trades = asyncio.run(load_trades(day_to_analyze, env))  # type:ignore
    if trades.empty:
        st.stop()

    algo_runs = asyncio.run(load_runs(day_to_analyze, env))  # type:ignore
    if algo_runs.empty:
        st.stop()

    st.success("load trading day data completed.")

if st.sidebar.checkbox("Show trades list"):
    st.write(trades)
if st.sidebar.checkbox("Show strategy executions"):
    st.write(algo_runs)

st.markdown("## How was my day?")
st.write("below is a list of daily sessions, with trades & total revenues.")
trade_details: Dict = {}

batch: Dict = {}
for index, row in trades.iterrows():
    algo_run_id = row["algo_run_id"]
    batch_id = row["batch_id"]
    symbol = row["symbol"]
    time = row["tstamp"]
    operation = row["operation"]
    price = row["price"]
    indicators = row["indicators"]
    qty = row["qty"]
    stop_price = row["stop_price"]
    target_price = row["target_price"]
    if algo_run_id not in trade_details:
        trade_details[algo_run_id] = {}
    if symbol not in trade_details[algo_run_id]:
        trade_details[algo_run_id][symbol] = []
    trade_details[algo_run_id][symbol].append(
        (operation, time, price, qty, indicators, stop_price, target_price)
    )
    if batch_id not in batch:
        batch[batch_id] = []
    if algo_run_id not in batch[batch_id]:
        batch[batch_id].append(algo_run_id)


revenues: Dict = {}
how_was_my_day = []
est = pytz.timezone("America/New_York")

try:
    for batch_id, count in batch.items():
        how_was_my_batch = pd.DataFrame()
        t = trades[trades["batch_id"] == batch_id]
        start_time = algo_runs[algo_runs.batch_id == batch_id].start_time
        start_time = pytz.utc.localize(start_time.min()).astimezone(est)
        how_was_my_batch["symbol"] = t.symbol.unique()
        how_was_my_batch["revenues"] = how_was_my_batch["symbol"].apply(
            lambda x: calc_batch_revenue(x, trades, batch_id)
        )
        how_was_my_batch["count"] = how_was_my_batch["symbol"].apply(
            lambda x: count_trades(x, trades, batch_id)
        )
        how_was_my_day.append(
            (
                batch_id,
                how_was_my_batch,
                start_time,
                algo_runs[algo_runs.batch_id == batch_id].algo_env.tolist()[0],
            )
        )
except ValueError as e:
    st.exception(e)
    st.error("Try picking another day")
    st.stop()
how_was_my_day.sort(key=lambda x: x[2])

for element in how_was_my_day:
    st.markdown(f"### [{element[3]}] {element[0]}")
    st.write(f"Start time {element[2]}")
    st.markdown(
        f"**TOTAL REVENUE** ${round(element[1]['revenues'].sum(), 2)} "
    )
    st.markdown(element[1].to_html(), unsafe_allow_html=True)

if st.sidebar.checkbox("Show details"):
    session = requests.session()
    dl = DataLoader(scale=TimeScale.minute)

    minute_history = {}

    c = 0
    with st.spinner(text="Loading historical data from Polygon..."):
        for batch_id, count in batch.items():
            for run_id in batch[batch_id]:
                symbols = trades.loc[trades["algo_run_id"] == run_id][
                    "symbol"
                ].value_counts()
                for symbol, count in symbols.items():
                    if symbol not in minute_history:
                        minute_history[symbol] = dl[symbol][
                            day_to_analyze  # type: ignore
                            - timedelta(days=7) : day_to_analyze  # type: ignore
                            + timedelta(days=1)
                        ]

                        c += 1
    st.success(f"LOADED {c} symbols' data!")

    for symbol in minute_history:
        symbol_df = trades.loc[trades["symbol"] == symbol]
        start_date = symbol_df["tstamp"].min().to_pydatetime()
        start_date = start_date.replace(hour=9, minute=30)
        end_date = start_date.replace(hour=16, minute=00)
        try:
            start_index = minute_history[symbol]["close"].index.get_loc(
                start_date, method="nearest"
            )
            end_index = minute_history[symbol]["close"].index.get_loc(
                end_date, method="nearest"
            )
        except Exception as e:
            print(f"Error for {symbol}: {e}")
            continue

        open_price = minute_history[symbol]["close"][start_index]

        fig, ax = plt.subplots()
        ax.plot(
            minute_history[symbol]["close"][
                start_index:end_index
            ].between_time("9:30", "16:00"),
            label=symbol,
        )
        # fig.xticks(rotation=45)

        delta = 0
        profit = 0

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
        resistance = None
        support = None

        for index, row in symbol_df.iterrows():
            delta = (
                row["price"]
                * row["qty"]
                * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
            )

            profit += delta
            ax.scatter(
                row["tstamp"].to_pydatetime(),
                row["price"],
                c="g" if row["operation"] == "buy" else "r",
                s=100,
            )
            deltas.append(round(delta, 2))
            profits.append(round(profit, 2))
            operations.append(row["operation"])
            times.append(
                pytz.utc.localize(pd.to_datetime(row["tstamp"])).astimezone(
                    est
                )
            )
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
            "profit": profits,
            "trade": deltas,
            "operation": operations,
            "at": times,
            "price": prices,
            "qty": qtys,
            "daily change": daily_change,
            "target price": target_price,
            "stop price": stop_price,
            "indicators": indicators,
        }
        st.write(f"{symbol} analysis with profit {round(profit, 2)}")
        st.markdown(pd.DataFrame(data=d).to_html(), unsafe_allow_html=True)
        st.pyplot(fig)
