from typing import List, Optional

import numpy as np
from pandas import DataFrame as df

import config
from tlog import tlog


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


def find_resistances(
    strategy_name: str, current_value: float, minute_history: df
) -> Optional[List[float]]:
    """calculate supports"""
    series = minute_history["high"][-200:].resample("5min").min()

    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] > current_value]
        )
        clusters = dict(enumerate(grouper(local_maximas), 1))

        resistances = []
        for key, cluster in clusters.items():
            if len(cluster) > 0:
                resistances.append(round(sum(cluster) / len(cluster), 2))
        resistances = sorted(resistances)

        if len(resistances) > 0:
            tlog(
                f"[{strategy_name}] find_resistances() - resistances={resistances}"
            )

        return resistances

    return None


def find_supports(
    strategy_name: str, current_value: float, minute_history: df
) -> Optional[List[float]]:
    """calculate supports"""
    series = minute_history["low"][-200:].resample("5min").min()
    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] <= current_value]
        )

        clusters = dict(enumerate(grouper(local_maximas), 1))
        resistances = []
        for key, cluster in clusters.items():
            if len(cluster) > 0:
                resistances.append(round(sum(cluster) / len(cluster), 2))
        resistances = sorted(resistances)

        if len(resistances) > 0:
            tlog(
                f"[{strategy_name}] find_supports() - resistances={resistances}"
            )

        return resistances

    return None


def find_stop(current_value, minute_history, now):
    """calculate stop loss"""
    series = minute_history["low"][-100:].dropna().resample("5min").min()
    series = series[now.floor("1D") :]
    diff = np.diff(series.values)
    low_index = np.where((diff[:-1] <= 0) & (diff[1:] > 0))[0] + 1
    if len(low_index) > 0:
        return series[low_index[-1]] - 0.01
    return current_value * config.default_stop
