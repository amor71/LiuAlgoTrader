from datetime import datetime

import hypothesis.strategies as st
import pandas as pd
import pytest
import pytz
from hypothesis import given, settings
from hypothesis.extra.pandas import indexes, series

from liualgotrader.fincalcs.trends import SeriesTrendType, get_series_trend


@settings(max_examples=200)
@given(
    series(
        index=indexes(
            elements=st.datetimes(
                min_value=datetime(2000, 1, 1), max_value=datetime(2040, 1, 1)
            ),
            dtype=None,
        ),
        elements=st.floats(
            allow_nan=False,
            allow_infinity=False,
        ),
        dtype=float,
    ),
)
@pytest.mark.devtest
def test_get_series_trend(serie: pd.Series):
    print(serie)
    r, t = get_series_trend(serie)
    print("result", r, t)
