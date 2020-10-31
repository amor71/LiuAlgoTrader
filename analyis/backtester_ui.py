import asyncio
import json
from datetime import date, timedelta

import alpaca_trade_api as tradeapi
import matplotlib.pyplot as plt
import nest_asyncio
import pandas as pd
import pygit2
import pytz
import requests
import streamlit as st
import toml
from streamlit.uploaded_file_manager import UploadedFile

from liualgotrader.analytics.analysis import (calc_batch_revenue, count_trades,
                                              load_batch_list, load_trades,
                                              load_trades_by_batch_id)
from liualgotrader.backtester import BackTestDay, backtest
from liualgotrader.common import config, database

try:
    config.build_label = pygit2.Repository("../").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
except pygit2.GitError:
    import liualgotrader

    config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
nest_asyncio.apply()

loop.run_until_complete(database.create_db_connection())
st.title("Liu Algo Trading Framework")
st.markdown("## **Back-testing & Analysis tools**")

app = st.sidebar.selectbox("select app", ("back-test", "analyzer"))

new_bid: str = ""
est = pytz.timezone("America/New_York")

if app == "back-test":
    env = st.sidebar.selectbox(
        "Select environment", ("PAPER", "BACKTEST", "PROD")
    )
    new_bid = ""
    st.text("Back-testing a past trading day, or a specific batch-id.")

    day_to_analyze = st.date_input("Pick day to analyze", value=date.today())

    selection = st.sidebar.radio(
        "Select back-testing mode",
        (
            "back-test a specific batch",
            "back-test against the whole day",
        ),
    )

    async def back_test():
        uploaded_file: UploadedFile = st.file_uploader(
            label="Select tradeplan file", type=["toml", "TOML"]
        )
        if uploaded_file:
            byte_str = uploaded_file.read()
            toml_as_string = byte_str.decode("UTF-8")

            if len(toml_as_string):
                conf_dict = toml.loads(toml_as_string)  # type: ignore

                if not conf_dict:
                    st.error("Failed to load TOML configuration file, retry")
                    st.stop()
            else:
                st.stop()
        else:
            st.stop()

        backtest = BackTestDay(conf_dict)
        new_bid = await backtest.create(day_to_analyze)
        while True:
            status, msgs = await backtest.next_minute()
            if not status:
                break
            if len(msgs) > 0:
                for msg in msgs:
                    if msg:
                        st.success(msg)

        await backtest.liquidate()
        st.success(f"new batch-id is {new_bid} -> view in the analyzer app")

    if selection == "back-test against the whole day":
        with st.spinner(f"back-testing.. patience is a virtue "):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(back_test())
    else:
        try:
            with st.spinner("Loading list of trading sessions"):
                df = load_batch_list(day_to_analyze, env)
            if df.empty:
                st.error("Select another day")
                st.stop()
        except Exception as e:
            st.error("Select another day")
            st.exception(e)
            st.stop()
        bid = st.selectbox(
            "select batch to backtest", df["batch_id"].unique().tolist()
        )
        if bid:
            how_was_my_day = pd.DataFrame()
            trades = load_trades(day_to_analyze, env)
            start_time = df[df.batch_id == bid].start_time
            start_time = pytz.utc.localize(start_time.min()).astimezone(est)
            how_was_my_day["symbol"] = trades.loc[trades["batch_id"] == bid][
                "symbol"
            ].unique()
            how_was_my_day["revenues"] = how_was_my_day["symbol"].apply(
                lambda x: calc_batch_revenue(x, trades, bid)
            )
            how_was_my_day["count"] = how_was_my_day["symbol"].apply(
                lambda x: count_trades(x, trades, env)
            )
            st.text(
                f"batch_id:{bid}\nstart time:{start_time }\nrevenue=${round(sum(how_was_my_day['revenues']), 2)}"
            )
            st.dataframe(how_was_my_day)

            uploaded_file: UploadedFile = st.file_uploader(
                label="Select tradeplan file", type=["toml", "TOML"]
            )
            if uploaded_file:
                byte_str = uploaded_file.read()
                toml_as_string = byte_str.decode("UTF-8")

                if len(toml_as_string):
                    conf_dict = toml.loads(toml_as_string)  # type: ignore

                    if not conf_dict:
                        st.error(
                            "Failed to load TOML configuration file, retry"
                        )
                        st.stop()
                else:
                    st.stop()
                with st.spinner(f"back-testing.."):
                    asyncio.set_event_loop(asyncio.new_event_loop())
                    try:
                        print(bid)
                        new_bid = backtest(bid, conf_dict=conf_dict)  # type: ignore
                    except Exception as e:
                        st.exception(e)
                        st.stop()

                    st.success(
                        f"new batch-id is {new_bid} -> view in the analyzer app"
                    )


elif app == "analyzer":
    st.text("Analyze a specific batch-id")

    show_trade_details = st.sidebar.checkbox("show trade details")
    bid = st.text_input("Enter batch-id", value=new_bid)

    if len(bid) > 0:
        est = pytz.timezone("America/New_York")
        utc = pytz.timezone("UTC")
        try:
            how_was_my_batch = pd.DataFrame()
            t = load_trades_by_batch_id(bid)

            if not len(t["client_time"].tolist()):
                st.info("No trades, $0 revenue")
                st.stop()

            if show_trade_details:
                st.dataframe(t)
            how_was_my_batch["symbol"] = t.symbol.unique()
            how_was_my_batch["revenues"] = how_was_my_batch["symbol"].apply(
                lambda x: calc_batch_revenue(x, t, bid)
            )
            how_was_my_batch["count"] = how_was_my_batch["symbol"].apply(
                lambda x: count_trades(x, t, bid)
            )
            st.dataframe(how_was_my_batch)
            st.text(
                f"Revenue: ${round(sum(how_was_my_batch['revenues'].tolist()), 2)}"
            )
        except Exception as e:
            st.error(f"Try picking another batch-id ({e})")
            st.stop()

        session = requests.session()
        api = tradeapi.REST(base_url="https://api.alpaca.markets")

        minute_history = {}

        c = 0

        day_to_analyze = min(t["client_time"].tolist())
        with st.spinner(text="Loading historical data from Polygon..."):
            for symbol in t.symbol.unique().tolist():
                if symbol not in minute_history:
                    minute_history[symbol] = api.polygon.historic_agg_v2(
                        symbol,
                        1,
                        "minute",
                        _from=day_to_analyze - timedelta(days=7),
                        to=day_to_analyze + timedelta(days=1),
                    ).df.tz_convert("US/Eastern")
                    c += 1
        st.success(f"LOADED {c} symbols' data!")

        for symbol in minute_history:
            symbol_df = t.loc[t["symbol"] == symbol]
            start_date = symbol_df["client_time"].min().to_pydatetime()
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
            for index, row in symbol_df.iterrows():
                resistance = None
                support = None
                delta = (
                    row["price"]
                    * row["qty"]
                    * (
                        1
                        if row["operation"] == "sell" and row["qty"] > 0
                        else -1
                    )
                )
                profit += delta

                ax.scatter(
                    row["client_time"].to_pydatetime(),
                    row["price"],
                    c="g" if row["operation"] == "buy" else "r",
                    s=100,
                )
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
