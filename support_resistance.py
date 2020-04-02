import numpy as np
from google.cloud.logging import logger

import config


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
    logger: logger.Logger,
    env: str,
    strategy_name: str,
    current_value,
    minute_history,
    now,
):
    """calculate supports"""
    minute_history_index = minute_history["high"].index.get_loc(
        now, method="nearest"
    )
    series = (
        minute_history["high"][
            minute_history_index - 200 : minute_history_index
        ]
        .resample("5min")
        .min()
    )
    logger.log_text(
        f"[{env}][{strategy_name}] find_resistances() - current_value={current_value} series = {series.values}"
    )
    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] > current_value]
        )

        logger.log_text(
            f"[{env}][{strategy_name}] find_resistances() - local_maximas={local_maximas}"
        )

        clusters = dict(enumerate(grouper(local_maximas), 1))

        logger.log_text(
            f"[{env}][{strategy_name}] find_resistances() - clusters={clusters}"
        )

        resistances = []
        for key, cluster in clusters.items():
            if len(cluster) > 1:
                resistances.append(round(sum(cluster) / len(cluster), 2))
        resistances = sorted(resistances)

        logger.log_text(
            f"[{env}][{strategy_name}] find_resistances() - resistances={resistances}"
        )

        return resistances

    logger.log_text(f"[{env}][{strategy_name}] find_supports() - None...")

    return None


def find_supports(
    logger: logger.Logger,
    env: str,
    strategy_name: str,
    current_value,
    minute_history,
    now,
):
    """calculate supports"""
    minute_history_index = minute_history["high"].index.get_loc(
        now, method="nearest"
    )
    series = (
        minute_history["high"][
            minute_history_index - 200 : minute_history_index
        ]
        .resample("5min")
        .min()
    )
    logger.log_text(
        f"[{env}][{strategy_name}] find_supports() - current_value={current_value} series = {series.values}"
    )
    diff = np.diff(series.values)
    high_index = np.where((diff[:-1] >= 0) & (diff[1:] <= 0))[0] + 1
    if len(high_index) > 0:
        local_maximas = sorted(
            [series[i] for i in high_index if series[i] <= current_value]
        )

        logger.log_text(
            f"[{env}][{strategy_name}] find_supports() - local_maximas={local_maximas}"
        )

        clusters = dict(enumerate(grouper(local_maximas), 1))

        logger.log_text(
            f"[{env}][{strategy_name}] find_supports() - clusters={clusters}"
        )

        resistances = []
        for key, cluster in clusters.items():
            if len(cluster) > 1:
                resistances.append(round(sum(cluster) / len(cluster), 2))
        resistances = sorted(resistances)

        logger.log_text(
            f"[{env}][{strategy_name}] find_supports() - resistances={resistances}"
        )

        return resistances

    logger.log_text(f"[{env}][{strategy_name}] find_supports() - None...")

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
