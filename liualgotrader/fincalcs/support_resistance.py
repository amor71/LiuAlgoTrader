from datetime import datetime, timedelta
from typing import List, Optional

import numpy as np
import pytz
from pandas import DataFrame as df
from pandas import Timestamp as ts

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


def grouper(iterable):
    prev = None
    group = []
    for item in iterable:

        if (
            not prev
            or -config.group_margin <= float(item - prev) / prev <= config.group_margin
        ):
            group.append(item)
        else:
            yield group
            group = [item]
        prev = item
    if group:
        yield group


async def find_resistances(
    symbol: str,
    strategy_name: str,
    current_value: float,
    minute_history: df,
    debug=False,
) -> Optional[List[float]]:
    """calculate supports"""

    est = pytz.timezone("America/New_York")
    back_time = ts(datetime.now(est)).to_pydatetime() - timedelta(days=3)
    back_time_index = minute_history["close"].index.get_loc(back_time, method="nearest")

    series = (
        minute_history["close"][back_time_index:]
        .dropna()
        .between_time("9:30", "16:00")
        .resample("15min")
        .max()
    ).dropna()

    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] >= current_value]
        )
        if len(local_maximas) > 0:
            if debug:
                tlog("find_resistances()")
                tlog(f"{minute_history}")
                tlog(f"{minute_history['close'][-1]}, {series}")
            # tlog(
            #    f"[{strategy_name}] find_resistances({symbol})={local_maximas}"
            # )
            return local_maximas

    return None


async def find_supports(
    symbol: str,
    strategy_name: str,
    current_value: float,
    minute_history: df,
    debug=False,
) -> List[float]:
    """calculate supports"""
    for back_track_min in range(120, len(minute_history.index), 60):
        series = (
            minute_history["close"][-back_track_min:]
            .dropna()
            .between_time("9:30", "16:00")
            .resample("15min")
            .min()
        ).dropna()
        diff = np.diff(series.values)
        high_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
        if len(high_index) > 0:
            local_maximas = sorted(
                [series[i] for i in high_index if series[i] <= current_value]
            )
            if len(local_maximas) > 0:
                if debug:
                    tlog("find_supports()")
                    tlog(f"{minute_history}")
                    tlog(f"{minute_history['close'][-1]}, {series}")
                # tlog(
                #    f"[{strategy_name}] find_supports({symbol})={local_maximas}"
                # )
                return local_maximas

    return []


def find_stop(current_value, minute_history, now):
    """calculate stop loss"""
    series = minute_history["low"][-100:].dropna().resample("5min").min()
    series = series[now.floor("1D") :]
    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(low_index) > 0:
        return series[low_index[-1]] - max(0.05, current_value * 0.02)
    return current_value * config.default_stop
