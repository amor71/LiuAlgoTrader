from datetime import datetime

import hypothesis.strategies as st
import pandas as pd
import pytz
from hypothesis import given, settings
from hypothesis.extra.pandas import columns, data_frames, indexes

from liualgotrader.fincalcs.resample import ResampleRangeType, resample

est = pytz.timezone("US/Eastern")


@settings(deadline=None, max_examples=100)
@given(
    data_frames(
        index=indexes(
            elements=st.datetimes(
                min_value=datetime(2000, 1, 1), max_value=datetime(2040, 1, 1)
            ),
            dtype=None,
        ),
        columns=columns(
            ["open", "close", "high", "low", "volume"], dtype=float
        ),
        rows=st.tuples(
            st.floats(allow_nan=True),
            st.floats(allow_nan=True),
            st.floats(allow_nan=True),
            st.floats(allow_nan=True),
            st.floats(allow_nan=True),
        ),
    ),
    st.sampled_from(ResampleRangeType),
)
def test_resample(ohlc: pd.DataFrame, resample_range: ResampleRangeType):
    print(ohlc.index)
    r = resample(ohlc, resample_range)
    if ohlc.empty:
        assert r.empty  # nosec
    else:
        assert not r.empty  # nosec

    print("result", r)
