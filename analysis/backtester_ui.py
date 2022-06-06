import asyncio

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
import json
import traceback

import alpaca_trade_api as tradeapi
import matplotlib.pyplot as plt
import pandas as pd
import pytz
import requests
import streamlit as st
import toml
from streamlit.uploaded_file_manager import UploadedFile

from liualgotrader.analytics.analysis import (calc_batch_revenue, count_trades,
                                              load_batch_list, load_trades,
                                              load_trades_by_batch_id)
from liualgotrader.common import config, database
from liualgotrader.common.data_loader import DataLoader  # type: ignore

loop.run_until_complete(database.create_db_connection())
st.title(f"LiuAlgoTrading Framework")
st.markdown("## **Visual Analysis tools**")

app = st.sidebar.selectbox("select app", ["analyzer"])

new_bid: str = ""
est = pytz.timezone("America/New_York")

if app == "analyzer":
    st.text("Analyze a batch-id")

    show_trade_details = st.sidebar.checkbox("show trade details")
    bid = st.text_input("Enter batch-id", value=new_bid)

    if len(bid) > 0:
        est = pytz.timezone("America/New_York")
        utc = pytz.timezone("UTC")
        try:
            how_was_my_batch = pd.DataFrame()
            t = loop.run_until_complete(load_trades_by_batch_id(bid))

            print(t)

            if t.empty:
                st.info("No trades, select another batch")
                st.stop()
            elif not len(t["client_time"].tolist()):
                st.info("No trades, $0 revenue")
                st.stop()
            elif show_trade_details:
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

        data_loader = DataLoader()
        day_to_analyze = min(t["client_time"].tolist())
        with st.spinner(text="Loading historical data"):
            for symbol in t.symbol.unique().tolist():
                if symbol not in minute_history:
                    minute_history[symbol] = data_loader[symbol]
                    c += 1
        st.success(f"LOADED {c} symbols' data!")
        est = pytz.timezone("US/Eastern")
        for symbol in minute_history:
            symbol_df = t.loc[t["symbol"] == symbol]
            start_date = symbol_df.client_time.min()
            end_date = symbol_df.client_time.max()
            # .astype(
            #    "datetime64[ns, US/Eastern]"
            # ).min()
            start_date = start_date.replace(
                hour=9, minute=30, second=0, microsecond=0
            )
            end_date = end_date.replace(hour=16, minute=00)
            symbol_data = minute_history[symbol][start_date:end_date]
            try:
                start_index = symbol_data.close.index.get_loc(
                    start_date, method="nearest"
                )
                end_index = symbol_data.close.index.get_loc(
                    end_date, method="nearest"
                )
            except Exception as e:
                traceback.print_exc()
                print(f"Error for {symbol}: {e}")
                continue

            open_price = symbol_data.close[start_index]

            fig, ax = plt.subplots()
            ax.plot(
                symbol_data.close[start_index:end_index],
                # .between_time("9:30", "16:00"),
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
                    row.client_time,  # .to_pydatetime(),
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
                "% change": daily_change,
                "target price": target_price,
                "stop price": stop_price,
                "indicators": indicators,
            }
            st.write(f"{symbol} analysis with profit {round(profit, 2)}")
            st.markdown(pd.DataFrame(data=d).to_html(), unsafe_allow_html=True)
            st.pyplot(fig)
