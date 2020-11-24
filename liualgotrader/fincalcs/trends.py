import math
from enum import Enum
from typing import Tuple

import numpy as np
import pandas as pd
import pytz
from scipy.stats import linregress

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog

est = pytz.timezone("US/Eastern")


class SeriesTrendType(Enum):
    UNKNOWN = 0
    SHARP_UP = 1
    UP = 2
    FLAT = 10
    DOWN = 20
    SHARP_DOWN = 21


def get_series_trend(series: pd.Series) -> Tuple[float, SeriesTrendType]:
    if len(series) < 4:
        return 0, SeriesTrendType.UNKNOWN

    length = min(10, len(series))
    try:
        np.seterr(all="raise")
        slope, _, _, _, _ = linregress(range(length), series[-length:])
        slope = round(slope, 2)
    except FloatingPointError:
        return math.inf, SeriesTrendType.UNKNOWN

    if -0.1 < slope < 0.1:
        t = SeriesTrendType.FLAT
    elif 0 < slope <= 1:
        t = SeriesTrendType.UP
    elif slope > 1:
        t = SeriesTrendType.SHARP_UP
    elif -1 <= slope < 0:
        t = SeriesTrendType.DOWN
    else:
        t = SeriesTrendType.SHARP_DOWN

    return slope, t
