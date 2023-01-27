import time
from datetime import datetime, timedelta

import pytest
from pytz import timezone

from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_multi_date_performance() -> None:
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.alpaca)

    t = time.time()
    dl["AAPL"][
        (datetime.now().date() - timedelta(days=20)) : (  # type: ignore
            datetime.now().date() - timedelta(days=10)  # type: ignore
        )
    ]

    pref_single_apple = time.time() - t
    print(f"load apple time spent {pref_single_apple}")

    t = time.time()
    dl["IBM"][
        (datetime.now().date() - timedelta(days=20)) : (  # type: ignore
            datetime.now().date() - timedelta(days=10)  # type: ignore
        )
    ]

    pref_single_ibm = time.time() - t
    print(f"load ibm time spent {pref_single_ibm}")

    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.alpaca)

    symbols = ["AAPL", "IBM", "TSLA", "WWBI"]
    end: datetime = datetime.now()
    start: datetime = end - timedelta(days=200)

    t = time.time()
    dl.pre_fetch(symbols=symbols, start=start, end=end)
    pref = time.time() - t
    print(f"load apple & ibm spent {pref}")

    t = time.time()
    dl["AAPL"]
    pref = time.time() - t
    print(f"multi 1 time spent {pref}")

    t = time.time()
    dl["AAPL"][
        (datetime.now().date() - timedelta(days=20)) : (  # type:ignore
            datetime.now().date() - timedelta(days=10)  # type:ignore
        )
    ]

    pref_multi = time.time() - t
    print(f"multi 2 time spent {pref_multi}")
