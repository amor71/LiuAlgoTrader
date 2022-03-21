from datetime import date

import pandas as pd
import pytest

from liualgotrader.common import config
from liualgotrader.common.types import (QueueMapper, TimeScale, WSConnectState,
                                        WSEventType)
from liualgotrader.data.polygon import PolygonData


@pytest.mark.devtest
def test_polygon_aapl_data_day() -> bool:
    polygon = PolygonData()
    print(
        polygon.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
            scale=TimeScale.day,
        )
    )
    return True


@pytest.mark.devtest
def test_polygon_aapl_data_min() -> bool:
    polygon = PolygonData()
    print(
        polygon.get_symbol_data(
            "AAPL",
            date(year=2021, month=2, day=1),
            date(year=2021, month=2, day=2),
        ).between_time("9:30", "16:00")
    )
    return True


@pytest.mark.devtest
def test_polygon_get_symbols() -> bool:
    polygon = PolygonData()
    symbols = polygon.get_symbols()
    print(f"{len(symbols)} symbols are retrieved from Polygon")
    return True


# this test may fail if your Polygon account is not in premium plan
@pytest.mark.devtest
def test_polygon_get_market_snapshot() -> bool:
    polygon = PolygonData()
    market_snapshots = polygon.get_market_snapshot()
    print(
        f"{len(market_snapshots)} tickers of market snapshots are retrieved from Polygon"
    )
    return True
