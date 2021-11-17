from datetime import datetime, timedelta

import pandas as pd
import pytest

from liualgotrader.common import config
from liualgotrader.fincalcs.vwap import add_daily_vwap, anchored_vwap


@pytest.mark.devtest
def test_add_daily_vwap_single_line() -> bool:
    print("test_add_daily_vwap_single_line")
    start = datetime.utcnow().replace(second=0, microsecond=0)
    end = start

    index = pd.date_range(start=start, end=end, freq="T")

    d = {
        "open": [10],
        "high": [20],
        "low": [10],
        "close": [20],
        "volume": [100],
    }
    df = pd.DataFrame(data=d, index=index)
    print(df)
    success = add_daily_vwap(df, back_time=start)
    print(df)
    if 50.0 / 3 != df.iloc[0].vwap:
        raise AssertionError(f"Unexpected VWAP {df.iloc[0].vwap}")
    if 50.0 / 3 != df.iloc[0].average:
        raise AssertionError(f"Unexpected average {df.iloc[0].average}")
    if not success:
        raise AssertionError("Why exception?")

    return True


@pytest.mark.devtest
def test_add_daily_vwap_two_line() -> bool:
    print("test_add_daily_vwap_two_line")
    start = datetime.utcnow().replace(second=0, microsecond=0)
    end = start + timedelta(minutes=1)

    index = pd.date_range(start=start, end=end, freq="T")

    d = {
        "open": [10, 10],
        "high": [20, 20],
        "low": [10, 10],
        "close": [20, 20],
        "volume": [100, 100],
    }
    print("index:", index)
    df = pd.DataFrame(data=d, index=index)
    print("df:", df)
    success = add_daily_vwap(df, back_time=start)
    print("df w/ vwap:", df)
    if 50.0 / 3 != df.iloc[1].vwap:
        raise AssertionError(f"Unexpected VWAP {df.iloc[1].vwap}")
    if 50.0 / 3 != df.iloc[1].average:
        raise AssertionError(f"Unexpected average {df.iloc[1].average}")
    if not success:
        raise AssertionError("Why exception?")

    return True


@pytest.mark.devtest
def test_add_daily_vwap_three_line() -> bool:
    print("test_add_daily_vwap_three_line")
    start = datetime.utcnow().replace(second=0, microsecond=0)
    end = start + timedelta(minutes=2)

    index = pd.date_range(start=start, end=end, freq="T")

    d = {
        "open": [10, 10, 10],
        "high": [20, 20, 50],
        "low": [10, 10, 5],
        "close": [20, 20, 70],
        "volume": [100, 100, 100],
    }
    print(index)
    df = pd.DataFrame(data=d, index=index)
    print(df)
    success = add_daily_vwap(df, debug=True, back_time=start)
    print(df)
    if df.iloc[2].vwap != 25.0:
        raise AssertionError(f"Unexpected VWAP {df.iloc[2].vwap}")

    if not success:
        raise AssertionError("Why exception?")

    return True


@pytest.mark.devtest
def test_anchored_vwap_three_line() -> bool:
    print("test_anchored_vwap_three_line")
    start = datetime.utcnow().replace(second=0, microsecond=0)
    end = start + timedelta(minutes=2)

    index = pd.date_range(start=start, end=end, freq="T")

    d = {
        "open": [10, 10, 10],
        "high": [20, 20, 50],
        "low": [10, 10, 5],
        "close": [20, 20, 70],
        "volume": [100, 100, 100],
    }
    print(index)
    df = pd.DataFrame(data=d, index=index)
    print(df)
    s = anchored_vwap(df, start, debug=True)
    print(s)
    if s[-1] != 25.0:
        raise AssertionError(f"Unexpected VWAP {s[-1]}")

    return True
