from datetime import datetime

import pandas as pd
from pandas import DataFrame as df
from pandas import Timestamp as ts

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


def add_daily_vwap(minute_data: df, debug=False) -> bool:
    back_time = ts(config.market_open)

    print("before vwap", minute_data)
    try:
        back_time_index = minute_data["close"].index.get_loc(
            back_time, method="nearest"
        )
    except Exception as e:
        if debug:
            tlog(
                f"IndexError exception {e} in add_daily_vwap for {minute_data}"
            )
        return False

    minute_data["pv"] = minute_data.apply(
        lambda x: (x["close"] + x["high"] + x["low"]) / 3 * x["volume"], axis=1
    )
    minute_data["apv"] = minute_data["pv"][back_time_index:].cumsum()
    minute_data["av"] = minute_data["volume"][back_time_index:].cumsum()

    minute_data["average"] = minute_data["apv"] / minute_data["av"]
    minute_data["vwap"] = minute_data.apply(
        lambda x: (x["close"] + x["high"] + x["low"]) / 3, axis=1
    )

    return True


def anchored_vwap(
    ohlc_data: df, start_time: datetime, debug=False
) -> pd.Series:
    try:
        start_time_index = ohlc_data["close"].index.get_loc(
            start_time, method="nearest"
        )
    except Exception as e:
        if debug:
            tlog(f"IndexError exception {e} in anchored_vwap for {ohlc_data}")
        return pd.Series()

    df = ohlc_data.copy()
    df["pv"] = df.apply(
        lambda x: (x["close"] + x["high"] + x["low"]) / 3 * x["volume"], axis=1
    )
    df["apv"] = df["pv"][start_time_index:].cumsum()
    df["av"] = df["volume"][start_time_index:].cumsum()

    df["average"] = df["apv"] / df["av"]

    return df.average[start_time_index:]
