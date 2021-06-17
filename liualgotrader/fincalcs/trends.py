import math
from datetime import datetime, timedelta
from enum import Enum
from typing import Tuple

import numpy as np
import pandas as pd
import pytz
from scipy.stats import linregress

from liualgotrader.common.data_loader import DataLoader  # type: ignore

est = pytz.timezone("US/Eastern")


class SeriesTrendType(Enum):
    UNKNOWN = 0
    SHARP_DOWN = 1
    DOWN = 5
    UP = 15
    SHARP_UP = 20


class VolatilityClassificationType(Enum):
    UNKNOWN = 0
    LOW = 1
    MEDIUM = 5
    HIGH = 10


def get_series_trend(series: pd.Series) -> Tuple[float, SeriesTrendType]:
    if len(series) < 4:
        return 0, SeriesTrendType.UNKNOWN

    try:
        np.seterr(all="raise")
        slope, _, _, _, _ = linregress(np.arange(len(series)), series)
        slope = round(slope, 3)
    except FloatingPointError:
        return math.inf, SeriesTrendType.UNKNOWN

    if 0 < slope <= 1.0:
        t = SeriesTrendType.UP
    elif slope > 1.0:
        t = SeriesTrendType.SHARP_UP
    elif -1.0 <= slope < 0:
        t = SeriesTrendType.DOWN
    else:
        t = SeriesTrendType.SHARP_DOWN

    return slope, t


def volatility(data_loader: DataLoader, symbol: str, now: datetime) -> float:
    return (
        data_loader[symbol]
        .close[now - timedelta(days=30) : now]  # type: ignore
        .pct_change()
        .rolling(20)
        .std()
        .iloc[-1]
    )
