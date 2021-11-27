import time
from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_multi_date_performance() -> bool:
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.alpaca)

    t = time.time()
    dl["AAPL"][
        datetime.today().date()  # type:ignore
        - timedelta(days=20) : datetime.today().date()  # type:ignore
        - timedelta(days=10)
    ]
    pref_single_apple = time.time() - t
    print(f"load apple time spent {pref_single_apple}")

    t = time.time()
    dl["IBM"][
        datetime.today().date()  # type:ignore
        - timedelta(days=20) : datetime.today().date()  # type:ignore
        - timedelta(days=10)
    ]
    pref_single_ibm = time.time() - t
    print(f"load ibm time spent {pref_single_ibm}")

    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.alpaca)

    symbols = ["AAPL", "IBM", "TSLA", "WWBI"]
    end = datetime.today().date()
    start = end - timedelta(days=200)

    t = time.time()
    dl.pre_fetch(symbols=symbols, start=start, end=end)
    pref = time.time() - t
    print(f"load apple & ibm spent {pref}")

    if pref > pref_single_ibm + pref_single_apple:
        raise AssertionError("performance improvement not proven")

    t = time.time()
    dl["AAPL"]
    pref = time.time() - t
    print(f"multi 1 time spent {pref}")

    t = time.time()
    dl["AAPL"][
        datetime.today().date()  # type:ignore
        - timedelta(days=20) : datetime.today().date()  # type:ignore
        - timedelta(days=10)
    ]
    pref_multi = time.time() - t
    print(f"multi 2 time spent {pref_multi}")

    return True
