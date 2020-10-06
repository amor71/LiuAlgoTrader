from pandas import DataFrame as df
from pandas import Timestamp as ts
from tabulate import tabulate
from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


def add_daily_vwap(minute_data: df, debug=False) -> bool:
    back_time = ts(config.market_open)

    try:
        back_time_index = minute_data["close"].index.get_loc(
            back_time, method="nearest"
        )
    except Exception as e:
        if debug:
            tlog(f"IndexError exception {e} in add_daily_vwap for {minute_data}")
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

    # print(f"\n{tabulate(minute_data, headers='keys', tablefmt='psql')}")
    if debug:
        tlog(f"\n{tabulate(minute_data[-110:-100], headers='keys', tablefmt='psql')}")
        tlog(f"\n{tabulate(minute_data[-10:], headers='keys', tablefmt='psql')}")

    return True
