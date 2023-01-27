from datetime import date, datetime, timedelta
from time import time
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from pytz import timezone
from tabulate import tabulate

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def testcreate_data_loader_default():
    DataLoader(connector=DataConnectorType.alpaca)


@pytest.mark.devtest
def test_apple_stock_daily_price():
    print("test_apple_stock_daily_price")
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.alpaca)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]
    before_price = dl["AAPL"][-5].close
    print(dl["AAPL"][-5], dl["AAPL"][-5].close, before_price)
    before_time = dl["AAPL"][-5].name
    print(dl["AAPL"][-5], dl["AAPL"][-5].close)
    print(
        f"apple {last_price} @ {last_price_time}, before was {before_price} @{before_time} "
    )
    df = dl["AAPL"]
    print(df)

    assert df.empty, "did not expect empty DataFrame"
    assert last_price_time - before_time == timedelta(
        days=4
    ), f"{last_price_time} - {before_time} : unexpected date different {last_price_time - before_time}"


@pytest.mark.devtest
def testapple_test2():
    print("testapple_test2")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    start = datetime(
        year=2020,
        month=10,
        day=1,
        hour=9,
        minute=30,
        tzinfo=ZoneInfo("US/Eastern"),
    )
    end = datetime(
        year=2020,
        month=10,
        day=1,
        hour=20,
        minute=0,
        tzinfo=ZoneInfo("US/Eastern"),
    )
    data = dl["AAPL"].close[start:end]  # type: ignore

    print(data)
    assert len(data) == 2, f"not enough data {len(data)}"


@pytest.mark.devtest
def testapple_test1():
    print("testapple_test1")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    data = dl["AAPL"].close[-10 : datetime.now(nyc).date()]  # type: ignore

    print(f"{str(datetime.now(nyc).date())}:{len(data)}")
    print(data)

    if len(data) != 10:
        raise AssertionError("not enough data")


@pytest.mark.devtest
def test_apple_stock_latestprice():
    print("test_apple_stock_latestprice")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"][-1].name

    print(f"apple {last_price} @ {last_price_time}")


@pytest.mark.devtest
def test_apple_stock_current_price():
    print("test_apple_stock_current_price")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"][-1].name
    before_price = dl["AAPL"].close[-5]
    before_price_time = dl["AAPL"][-5].name

    print(
        f"apple {last_price} @ {last_price_time}, before was {before_price}@{before_price_time}"
    )


@pytest.mark.devtest
def test_apple_stock_current_price_range_int_minute():
    print("test_apple_stock_current_price_range_int_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[-5:-1]  # type:ignore

    print(last_price_range)

    assert len(last_price_range) == 5, "incorrect amount of data"


@pytest.mark.devtest
def test_apple_stock_current_price_range_int_day():
    print("test_apple_stock_current_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[-6:-1]  # type:ignore
    print(last_price_range)

    assert len(last_price_range) == 6, "incorrect amount of data"


@pytest.mark.devtest
def test_day_num_data_points():
    print("test_day_num_data_points")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    data = dl["AAPL"].close[-90:]  # type:ignore

    if 90 >= len(data) >= 89:
        return

    raise AssertionError(f"expected 90 data points, received only {len(data)}")


@pytest.mark.devtest
def test_day_num_data_points_w_date():
    print("test_day_num_data_points_w_date")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    data = dl["AAPL"].close[-90:"2021-09-10 09:30:00"]  # type:ignore

    if len(data) != 90:
        raise AssertionError(
            f"expected 90 data points, received only {len(data)}"
        )


@pytest.mark.devtest
def test_negative_current_price():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    try:
        dl["DFGDFGDFG"].close[-1]
    except ValueError:
        return

    raise AssertionError("expected failure")


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_day():
    print("test_apple_stock_close_price_range_str_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[
        "2021-01-01":"2021-01-05"  # type:ignore
    ]  # type:ignore

    assert len(last_price_range) == 2, "expected 2 data points"
    print(last_price_range, len(last_price_range))


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_minute():
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[
        "2021-01-05 09:45:00":"2021-01-05 09:50:00"  # type:ignore
    ]

    assert len(last_price_range) == 6, "expected 6 data points"
    print(last_price_range, len(last_price_range))


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_minute_int():
    print("test_apple_stock_close_price_range_str_minute_int")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    t0 = time()
    last_price_range = dl["AAPL"].close[
        "2021-12-15 09:45:00":-1  # type:ignore
    ]  # type:ignore
    t1 = time()
    duration = t1 - t0
    print(f"{last_price_range} in {duration} seconds")
    assert duration < 120.0, f"duration {duration} is too long"


@pytest.mark.devtest
def test_apple_stock_price_range_int_minute():
    print("test_apple_stock_price_range_int_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(f"{last_price_range}, data points {len(last_price_range)}")
    assert len(last_price_range) == 5, "expected 5 data points"


@pytest.mark.devtest
def test_apple_stock_price_range_int_day():
    print("test_apple_stock_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(f"{last_price_range}, data points {len(last_price_range)}")
    assert len(last_price_range) == 5, "expected 5 data points"


@pytest.mark.devtest
def test_apple_stock_price_range_date_day():
    print("test_apple_stock_price_range_date_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"]["2020-10-05":"2020-10-08"]  # type:ignore
    print(f"{last_price_range}, data points {len(last_price_range)}")
    assert len(last_price_range) == 4, "expected 4 data points"


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_day():
    print("test_apple_stock_price_range_date_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    t0 = time()
    last_price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    duration = time() - t0
    print(f"{last_price_range} in {duration} seconds")
    assert duration < 25.0, f"duration {duration} is too long"


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_min_open():
    print("test_apple_stock_price_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    t0 = time()
    last_price_range = dl["AAPL"]["2020-10-05":]  # type:ignore
    duration = time() - t0
    print(f"{last_price_range} in {duration} seconds")
    assert duration < 180.0, f"duration {duration} is too long"


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_int_min_open():
    print("test_apple_stock_price_open_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    t0 = time()
    last_price_range = dl["AAPL"].open["2020-10-05":]  # type:ignore
    duration = time() - t0
    print(f"{last_price_range} in {duration} seconds")
    assert duration < 180.0, f"duration {duration} is too long"


@pytest.mark.devtest
def test_apple_stock_price_range_date_min_open():
    print("test_apple_stock_price_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"][:]  # type:ignore
    print(f"{last_price_range}, data points {len(last_price_range)}")


@pytest.mark.devtest
def test_apple_stock_price_range_date_min():
    print("test_apple_stock_price_range_date_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    d2 = date(year=2021, month=2, day=2)
    last_price_range = dl["AAPL"][d1:d2].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore

    num_data_points = len(last_price_range)
    print(f"{last_price_range}, data points {num_data_points}")
    assert (
        num_data_points == 391
    ), f"expected 391 data-points but got {num_data_points}"


@pytest.mark.devtest
def test_apple_stock_price_range_date_min_mixed():
    print("test_apple_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][d1:"2021-02-02"].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore

    num_data_points = len(last_price_range)
    print(f"{last_price_range}, data points {num_data_points}")
    assert (
        num_data_points == 391
    ), f"expected 391 data-points but got {num_data_points}"


@pytest.mark.devtest
def test_apple_stock_price_range_date_day_mixed():
    print("test_apple_stock_price_range_date_day_mixed")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][d1:"2021-02-02"]  # type:ignore
    num_data_points = len(last_price_range)
    print(f"{last_price_range}, data points {num_data_points}")
    assert (
        num_data_points == 2
    ), f"expected 391 data-points but got {num_data_points}"


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_min_mixed():
    print("test_apple_stock_price_open_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = datetime(year=2021, month=2, day=1, hour=3, minute=0)
    last_price_range = (
        dl["AAPL"]
        .open[d1:"2021-02-01 21:00:00"]  # type:ignore
        .between_time("9:30", "16:00")  # type:ignore
    )
    num_data_points = len(last_price_range)
    print(f"{last_price_range}, data points {num_data_points}")
    assert (
        num_data_points == 391
    ), f"expected 391 data-points but got {num_data_points}"


@pytest.mark.devtest
def test_apple_stock_price_open_str():
    print("test_apple_stock_price_open_str")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"].open["2021-02-02 09:45:00"]
    print(f"{last_price_range}")


@pytest.mark.devtest
def test_apple_stock_price_open_date():
    print("test_apple_stock_price_open_date")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = nyc.localize(datetime(year=2021, month=2, day=1, hour=9, minute=30))
    last_price_range = dl["AAPL"].open[d1]
    print(last_price_range)
    assert (
        last_price_range == 132.16
    ), f"got unexpected value {last_price_range}"


@pytest.mark.devtest
def test_apple_update():
    print("test_apple_update")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    _ = dl["AAPL"][-1]

    dl["AAPL"].loc["2021-02-02 09:46:00"] = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]
    print(dl["AAPL"].loc["2021-02-02 09:46:00"])
    assert (
        dl["AAPL"].loc["2021-02-02 09:46:00"].close == 100.0
    ), f'unexpected value {dl["AAPL"].loc["2021-02-02 09:46:00"].close}'
