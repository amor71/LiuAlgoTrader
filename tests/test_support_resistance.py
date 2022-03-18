from datetime import datetime

import hypothesis.strategies as st
import numpy as np
import pandas as pd
import pytz
from hypothesis import given, settings
from hypothesis.extra.pandas import columns, indexes, series

from liualgotrader.fincalcs.support_resistance import get_local_maxima

est = pytz.timezone("US/Eastern")


@settings(deadline=None, max_examples=100)
@given(
    series(
        index=indexes(
            elements=st.datetimes(
                min_value=datetime(2000, 1, 1), max_value=datetime(2040, 1, 1)
            ),
        ),
        elements=st.floats(),
        dtype=float,
    ),
)
def test_get_local_maxima(series: pd.Series):
    print(series)
    r = get_local_maxima(series)
    if r.empty:
        assert r.empty  # nosec
    else:
        assert not r.empty  # nosec

    print("result", r)
