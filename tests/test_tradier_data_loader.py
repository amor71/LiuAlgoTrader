from datetime import date, datetime

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_create_data_loader_default() -> bool:
    return bool(DataLoader(connector=DataConnectorType.tradier))


@pytest.mark.devtest
def test_apple_stock_latest_price() -> bool:
    print("test_apple_stock_latest_price")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]

    print(f"apple {last_price} @ {last_price_time}")

    return True


@pytest.mark.devtest
def test_apple_stock_current_price() -> bool:
    print("test_apple_stock_current_price")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]
    before_price = dl["AAPL"].close[-5]
    before_price_time = dl["AAPL"].close.index[-5]

    print(
        f"apple {last_price} @ {last_price_time}, before was {before_price}@{before_price_time}"
    )

    return True


@pytest.mark.devtest
def test_apple_stock_current_price_range_int_minute() -> bool:
    print("test_apple_stock_current_price_range_int_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"].close[-5:-1]  # type:ignore

    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_current_price_range_int_day() -> bool:
    print("test_apple_stock_current_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"].close[-6:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_day_num_data_points() -> bool:
    print("test_day_num_data_points")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    data = dl["AAPL"].close[-90:]  # type:ignore

    if len(data) != 90:
        raise AssertionError(
            f"expected 90 datapoints, received only {len(data)}"
        )

    return True


@pytest.mark.devtest
def test_day_num_data_points_w_date() -> bool:
    print("test_day_num_data_points")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    data = dl["AAPL"].close[-90:"2021-09-10 09:30:00"]  # type:ignore

    if len(data) != 90:
        raise AssertionError(
            f"expected 90 datapoints, received only {len(data)}"
        )

    return True


@pytest.mark.devtest
def no_test_apple_stock_daily_price() -> bool:
    print("test_apple_stock_daily_price")
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.tradier)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]
    print(last_price, last_price_time)
    before_price = dl["AAPL"].close[-5]
    print(f"before_price {before_price}, {dl['AAPL']}")
    print(f"apple {last_price} @ {last_price_time}, before was {before_price}")

    return True


@pytest.mark.devtest
def test_negative_current_price() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    try:
        dl["DFGDFGDFG"].close[-1]
    except ValueError:
        return True

    return False


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_day() -> bool:
    print("test_apple_stock_close_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"].close[
        "2021-01-01":"2021-01-05"  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_int_minute() -> bool:
    print("test_apple_stock_price_range_int_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_int_day() -> bool:
    print("test_apple_stock_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_day() -> bool:
    print("test_apple_stock_price_range_date_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"]["2020-10-05":"2020-10-08"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_day() -> bool:
    print("test_apple_stock_price_range_date_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.tradier)
    last_price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_min_open() -> bool:
    print("test_apple_stock_price_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    try:
        last_price_range = dl["AAPL"][:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_min_open() -> bool:
    print("test_apple_stock_price_open_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.tradier)
    try:
        last_price_range = dl["AAPL"].open[:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True
