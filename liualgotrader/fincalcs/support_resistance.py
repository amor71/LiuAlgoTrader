from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd
import pytz
from pandas import DataFrame as df
from pandas import Timestamp as ts

from liualgotrader.common import config

est = pytz.timezone("US/Eastern")


class StopRangeType(Enum):
    LAST_100_MINUTES = 1
    LAST_2_HOURS = 2
    LAST_3_HOURS = 3
    DAILY = 10
    WEEKLY = 20
    DATE_RANGE = 50


def grouper(iterable):
    prev = None
    group = []
    for item in iterable:

        if (
            not prev
            or -config.group_margin
            <= float(item - prev) / prev
            <= config.group_margin
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
    back_time_index = minute_history["close"].index.get_loc(
        back_time, method="nearest"
    )

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
            return local_maximas

    return None


def find_supports(
    current_value,
    minute_history,
    now: datetime,
    range_type: StopRangeType = StopRangeType.LAST_100_MINUTES,
):
    # get low Series based on select time-range
    if range_type == StopRangeType.DAILY:
        series = (
            minute_history["low"][
                ts(
                    now.replace(
                        hour=9, minute=30, second=0, microsecond=0, tzinfo=est
                    )
                ) :
            ]
            .resample("5min")
            .min()
        )
    elif range_type == StopRangeType.LAST_100_MINUTES:
        series = minute_history["low"][-100:].dropna().resample("5min").min()
        series = series[ts(now).floor("1D") :]
    elif range_type == StopRangeType.LAST_2_HOURS:
        series = minute_history["low"][-120:].dropna().resample("5min").min()
        series = series[ts(now).floor("1D") :]
    elif range_type == StopRangeType.LAST_3_HOURS:
        series = minute_history["low"][-180:].dropna().resample("5min").min()
        series = series[ts(now).floor("1D") :]
    else:
        raise NotImplementedError(
            f"stop-range type {range_type} is not implemented"
        )

    # find local minima
    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(low_index) > 0:
        return [series[x] for x in low_index if series[x] < current_value]
    return None


def find_stop(
    current_value,
    minute_history,
    now: datetime,
    range_type: StopRangeType = StopRangeType.LAST_100_MINUTES,
):
    if range_type in (StopRangeType.DATE_RANGE, StopRangeType.WEEKLY):
        raise NotImplementedError(
            f"stop-range type {range_type} is not implemented"
        )

    if range_type == StopRangeType.DAILY:
        series = (
            minute_history["low"][
                ts(
                    now.replace(
                        hour=9, minute=30, second=0, microsecond=0, tzinfo=est
                    )
                ) :
            ]
            .dropna()
            .resample("5min")
            .min()
        )
    else:
        series = minute_history["low"][-100:].dropna().resample("5min").min()
        series = series[ts(now).floor("1D") :]

    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(low_index) > 0:
        return series[low_index[-1]]  # - max(0.05, current_value * 0.02)
    return None  # current_value * config.default_stop


def get_local_maxima(
    series: pd.Series,
    debug=False,
) -> pd.Series:
    """calculate local maximal point"""
    if series.empty:
        return pd.Series([], dtype=np.float64)

    series = series.resample("5min").max()
    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1

    return (
        pd.Series(
            index=[series.index[i] for i in high_index],
            data=[series[i] for i in high_index],
            dtype=np.float64,
        )
        if len(high_index) > 0
        else pd.Series([], dtype=np.float64)
    )
