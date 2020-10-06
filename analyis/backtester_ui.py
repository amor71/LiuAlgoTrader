import streamlit as st
import asyncio
import io
import pandas as pd
import alpaca_trade_api as tradeapi
import requests
import pygit2
import toml
import pytz
import matplotlib.pyplot as plt
from typing import Dict
from datetime import date, timedelta
from liualgotrader.analytics.analysis import (
    load_batch_list,
    load_trades,
    calc_revenue,
    count_trades,
    load_trades_by_batch_id,
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

app = st.sidebar.selectbox("select app", ("back-test", "analyzer"))
new_bid : str = ""
if app == 'back-test':
    new_bid = ""
    st.text("Back-testing a past trading day, or a specific batch-id")
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
                    new_bid = backtest(bid, conf_dict=conf_dict)
                    st.success(f"new batch-id is {new_bid}")

elif app == 'analyzer':
    st.text("Analyze a specific batch-id")

    shpw_trade_details = st.sidebar.checkbox("show trade details")
    bid = st.text_input("Enter batch-id", value=new_bid)

    if len(bid) > 0:
        est = pytz.timezone("America/New_York")
        utc = pytz.timezone("UTC")
        try:
            how_was_my_batch = pd.DataFrame()
            t = load_trades_by_batch_id(bid)
            t['client_time'] = pd.to_datetime(t['client_time'])
            if shpw_trade_details:
                st.dataframe(t)
            how_was_my_batch["symbol"] = t.symbol.unique()
            how_was_my_batch["revenues"] = how_was_my_batch["symbol"].apply(
                lambda x: calc_revenue(x, t)
            )
            how_was_my_batch["count"] = how_was_my_batch["symbol"].apply(
                lambda x: count_trades(x, t)
            )
            st.dataframe(how_was_my_batch)
        except Exception as e:
            st.error(f"Try picking another batch-id ({e})")
            st.stop()

        session = requests.session()
        api = tradeapi.REST(base_url="https://api.alpaca.markets")

        minute_history = {}

        c = 0
        day_to_analyze = min(t['client_time'].tolist())
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

        position = {}
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
                minute_history[symbol]["close"][start_index:end_index].between_time(
                    "9:30", "16:00"
                ),
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
            position[symbol] = 0
            for index, row in symbol_df.iterrows():
                resistance = None
                support = None
                if not position[symbol]:
                    try:
                        now = int(row["client_time"])
                        continue
                    except Exception:
                        pass

                if position[symbol] >= 0 and row["operation"] == "buy":
                    delta = -row["price"] * row["qty"]
                    position[symbol] += row["qty"]
                elif position[symbol] <= 0 and row["operation"] == "sell":
                    delta = row["price"] * row["qty"]
                    position[symbol] -= row["qty"]
                elif position[symbol] > 0 and row["operation"] == "sell":
                    delta = row["price"] * row["qty"]
                    position[symbol] -= row["qty"]
                elif position[symbol] < 0 and row["operation"] == "buy":
                    delta = -row["price"] * row["qty"]
                    position[symbol] += row["qty"]

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
                indicators.append(row["indicators"])
                target_price.append(row["target_price"])
                stop_price.append(row["stop_price"])
                daily_change.append(
                    f"{round(100.0 * (row['price'] - open_price) / open_price, 2)}%"
                )
                precent_vwap.append(
                    f"{round(100.0 * (row['indicators']['avg'] - open_price) / open_price, 2)}%"
                    if "avg" in row["indicators"]
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
