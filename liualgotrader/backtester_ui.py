import streamlit as st
import asyncio
import io
import pandas as pd

import pygit2
import toml
from typing import Dict
from datetime import date
from liualgotrader.analytics.analysis import (
    load_batch_list,
    load_trades,
    calc_revenue,
    count_trades,
)
from liualgotrader.common import config
from liualgotrader.backtester import backtest

try:
    config.build_label = pygit2.Repository("../").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
except pygit2.GitError:
    import liualgotrader

    config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore

st.title("Back-testing a trading session")

# Select date
day_to_analyze = st.date_input("pick day to analyze", value=date.today())

# Load configuration
st.set_option("deprecation.showfileUploaderEncoding", False)
file_buffer: io.StringIO = st.file_uploader(
    label="select tradeplan file", type=["toml", "TOML"]
)
if not file_buffer:
    st.error("Failed to load file, retry")
    st.stop()

try:
    toml_as_stringio = file_buffer.read()
    conf_dict: Dict = toml.loads(toml_as_stringio)

    if not conf_dict:
        st.error("Failed to load TOML configuration file, retry")
        st.stop()
except Exception as e:
    st.exception(e)
    st.stop()

selection = st.sidebar.radio(
    "Select back-testing mode",
    (
        "back-test a specific batch",
        "back-test against the whole day",
    ),
)

if selection == "back-test against the whole day":
    st.error("Not implemented yet")
    st.stop()
else:
    try:
        with st.spinner("Loading list of trading sessions"):
            df = load_batch_list(day_to_analyze)
        if df.empty:
            st.error("Select another day")
            st.stop()
    except Exception as e:
        st.error("Select another day")
        st.exception(e)
        st.stop()

    bid = st.selectbox("select batch to backtest", df["batch_id"].tolist())
    if bid:
        how_was_my_day = pd.DataFrame()
        trades = load_trades(day_to_analyze)
        how_was_my_day["symbol"] = trades.loc[trades["batch_id"] == bid][
            "symbol"
        ].unique()
        how_was_my_day["revenues"] = how_was_my_day["symbol"].apply(
            lambda x: calc_revenue(x, trades)
        )
        how_was_my_day["count"] = how_was_my_day["symbol"].apply(
            lambda x: count_trades(x, trades)
        )
        st.text(
            f"batch_id:{bid}, total revenues=${round(sum(how_was_my_day['revenues']), 2)}"
        )
        st.dataframe(how_was_my_day)

        if st.button("GO!"):
            with st.spinner(f"back-testing.."):
                asyncio.set_event_loop(asyncio.new_event_loop())
                new_id = backtest(bid, conf_dict=conf_dict)
                st.success(f"new batch-id is {new_id}")
