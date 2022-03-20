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
    return bool(DataLoader(connector=DataConnectorType.alpaca))


@pytest.mark.devtest
def test_apple_test1() -> bool:
    print("test_apple_test1")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    data = dl["AAPL"].close[-10 : datetime.now(nyc).date()]  # type: ignore

    print(f"{str(datetime.now(nyc).date())}:{len(data)}")
    print(data)

    if len(data) != 10:
        raise AssertionError("not enough data")

    return True


@pytest.mark.devtest
def test_apple_stock_latest_price() -> bool:
    print("test_apple_stock_latest_price")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]

    print(f"apple {last_price} @ {last_price_time}")

    return True


@pytest.mark.devtest
def test_apple_stock_current_price() -> bool:
    print("test_apple_stock_current_price")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
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
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[-5:-1]  # type:ignore

    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_current_price_range_int_day() -> bool:
    print("test_apple_stock_current_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[-6:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_day_num_data_points() -> bool:
    print("test_day_num_data_points")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    data = dl["AAPL"].close[-90:]  # type:ignore

    if 90 >= len(data) >= 89:
        return True

    raise AssertionError(f"expected 90 datapoints, received only {len(data)}")


@pytest.mark.devtest
def test_day_num_data_points_w_date() -> bool:
    print("test_day_num_data_points")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    data = dl["AAPL"].close[-90:"2021-09-10 09:30:00"]  # type:ignore

    if len(data) != 90:
        raise AssertionError(
            f"expected 90 datapoints, received only {len(data)}"
        )

    return True


@pytest.mark.devtest
def no_test_apple_stock_daily_price() -> bool:
    print("test_apple_stock_daily_price")
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.alpaca)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]
    print(last_price, last_price_time)
    before_price = dl["AAPL"].close[-5]
    print(f"before_price {before_price}, {dl['AAPL']}")
    print(f"apple {last_price} @ {last_price_time}, before was {before_price}")

    return True


@pytest.mark.devtest
def test_negative_current_price() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    try:
        dl["DFGDFGDFG"].close[-1]
    except ValueError:
        return True

    return False


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_day() -> bool:
    print("test_apple_stock_close_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[
        "2021-01-01":"2021-01-05"  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_minute() -> bool:
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[
        "2021-01-05 09:45:00":"2021-01-05 09:50:00"  # type:ignore
    ]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_minute_int() -> bool:
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].close[
        "2021-12-15 09:45:00":-1  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_int_minute() -> bool:
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_int_day() -> bool:
    print("test_apple_stock_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_day() -> bool:
    print("test_apple_stock_price_range_date_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"]["2020-10-05":"2020-10-08"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_day() -> bool:
    print("test_apple_stock_price_range_date_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_min() -> bool:
    print("test_apple_stock_price_range_date_int_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_min_open() -> bool:
    print("test_apple_stock_price_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"]["2020-10-05":]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_int_min_open() -> bool:
    print("test_apple_stock_price_close_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    last_price_range = dl["AAPL"].open["2020-10-05":]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_min_open() -> bool:
    print("test_apple_stock_price_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    try:
        last_price_range = dl["AAPL"][:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_min_open() -> bool:
    print("test_apple_stock_price_open_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    try:
        last_price_range = dl["AAPL"].open[:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_min() -> bool:
    print("test_apple_stock_price_range_date_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    d2 = date(year=2021, month=2, day=2)
    last_price_range = dl["AAPL"][d1:d2].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_min_mixed() -> bool:
    print("test_apple_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][d1:"2021-02-02"].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_day_mixed() -> bool:
    print("test_apple_stock_price_range_date_day_mixed")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][d1:"2021-02-02"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_min_mixed() -> bool:
    print("test_apple_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = datetime(year=2021, month=2, day=1, hour=3, minute=0)
    last_price_range = (
        dl["AAPL"]
        .open[d1:"2021-02-01 21:00:00"]  # type:ignore
        .between_time("9:30", "16:00")  # type:ignore
    )
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_open_str() -> bool:
    print("test_apple_stock_price_open_str")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"].open["2021-02-02 09:45:00"]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_open_date() -> bool:
    print("test_apple_stock_price_open_date")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = nyc.localize(datetime(year=2021, month=2, day=1, hour=9, minute=30))
    last_price_range = dl["AAPL"].open[d1]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_get_symbols_alpaca() -> bool:
    print("test_get_symbols_alpaca")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    tickers = dl.data_api.get_symbols()
    print(len(tickers))

    return True


@pytest.mark.devtest
def test_apple_update() -> bool:
    print("test_apple_stock_price_open_str")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    d1 = date(year=2021, month=2, day=1)
    dl["AAPL"][-1]
    print("after this")
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

    return True
