import time

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


def test_stock_price_range_date_min() -> bool:
    print("test_stock_price_range_date_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    t = time.time()
    price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(f"duration {time.time()-t}: {price_range}")

    dl = DataLoader(
        TimeScale.minute, connector=DataConnectorType.alpaca, concurrency=10
    )

    t = time.time()
    price_range_con = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(f"duration {time.time()-t}: {price_range_con}")

    print(
        "items in concurrent not in sequential load:",
        price_range_con.loc[
            price_range_con.index.difference(price_range.index)
        ],
    )
    print(
        "items ins sequential load not in concurrent:",
        price_range.index.difference(price_range_con.index),
    )

    if not (0 <= len(price_range_con) - len(price_range) <= 1):
        raise AssertionError("found issue loading data, please investigate")

    return True
