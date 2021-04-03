from datetime import date, datetime

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_create_data_loader_default() -> bool:
    config.data_connector = DataConnectorType.alpaca
    return bool(DataLoader())


@pytest.mark.devtest
def test_create_data_loader_types() -> bool:
    for data_connector in DataConnectorType:
        config.data_connector = data_connector
        for scale in TimeScale:
            if not DataLoader(scale=scale):
                return False

    config.data_connector = DataConnectorType.alpaca
    return True


@pytest.mark.devtest
def test_apple_stock_current_price() -> bool:
    config.data_connector = DataConnectorType.alpaca
    dl = DataLoader(TimeScale.minute)
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
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"].close[-5:-1]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_current_price_range_int_day() -> bool:
    config.data_connector = DataConnectorType.alpaca
    print("test_apple_stock_current_price_range_int_day")
    dl = DataLoader(TimeScale.day)
    last_price_range = dl["AAPL"].close[-6:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_daily_price() -> bool:
    config.data_connector = DataConnectorType.alpaca
    print("test_apple_stock_daily_price")
    dl = DataLoader(scale=TimeScale.day)
    last_price = dl["AAPL"].close[-1]
    last_price_time = dl["AAPL"].close.index[-1]
    before_price = dl["AAPL"].close[-5]
    before_price_time = dl["AAPL"].close.index[-5]
    print(
        f"apple {last_price} @ {last_price_time}, before was {before_price}@{before_price_time}"
    )

    return True


@pytest.mark.devtest
def test_negative_current_price() -> bool:
    config.data_connector = DataConnectorType.alpaca
    dl = DataLoader(TimeScale.minute)
    try:
        dl["DFGDFGDFG"].close[-1]
    except ValueError:
        return True

    return False


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_day() -> bool:
    config.data_connector = DataConnectorType.alpaca
    print("test_apple_stock_close_price_range_int_day")
    dl = DataLoader(TimeScale.day)
    last_price_range = dl["AAPL"].close[
        "2021-01-01":"2021-01-05"  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_minute() -> bool:
    config.data_connector = DataConnectorType.alpaca
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"].close[
        "2021-01-05 09:45:00":"2021-01-05 09:50:00"  # type:ignore
    ]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_close_price_range_str_minute_int() -> bool:
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"].close[
        "2021-01-05 09:45:00":-1  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_close_price_range_int_str_minute() -> bool:
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"].close[
        -5 : str(datetime.now())  # type:ignore
    ]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_int_minute() -> bool:
    print("test_apple_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_int_day() -> bool:
    print("test_apple_stock_price_range_int_day")
    dl = DataLoader(TimeScale.day)
    last_price_range = dl["AAPL"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_day() -> bool:
    print("test_apple_stock_price_range_date_day")
    dl = DataLoader(TimeScale.day)
    last_price_range = dl["AAPL"]["2020-10-05":"2020-10-08"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_day() -> bool:
    print("test_apple_stock_price_range_date_int_day")
    dl = DataLoader(TimeScale.day)
    last_price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_min() -> bool:
    print("test_apple_stock_price_range_date_int_min")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"]["2020-10-05":-1]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_min_open() -> bool:
    print("test_apple_stock_price_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"]["2020-10-05":]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_int_min_open() -> bool:
    print("test_apple_stock_price_close_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute)
    last_price_range = dl["AAPL"].open["2020-10-05":]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_min_open() -> bool:
    print("test_apple_stock_price_range_date_min_open")
    dl = DataLoader(TimeScale.minute)
    try:
        last_price_range = dl["AAPL"][:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_min_open() -> bool:
    print("test_apple_stock_price_open_range_date_min_open")
    dl = DataLoader(TimeScale.minute)
    try:
        last_price_range = dl["AAPL"].open[:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_min() -> bool:
    print("test_apple_stock_price_range_date_min")
    dl = DataLoader(TimeScale.minute)
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
    dl = DataLoader(TimeScale.minute)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][d1:"2021-02-02"].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_day_mixed() -> bool:
    print("test_apple_stock_price_range_date_day_mixed")
    dl = DataLoader(TimeScale.day)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][d1:"2021-02-02"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_open_range_date_min_mixed() -> bool:
    print("test_apple_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = (
        dl["AAPL"]
        .open[d1:"2021-02-02"]  # type:ignore
        .between_time("9:30", "16:00")  # type:ignore
    )
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_open_str() -> bool:
    print("test_apple_stock_price_open_str")
    dl = DataLoader(TimeScale.minute)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"].open["2021-02-02 09:45:00"]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_open_date() -> bool:
    print("test_apple_stock_price_open_date")
    dl = DataLoader(TimeScale.minute)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"].open[d1]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_get_symbols_polygon() -> bool:
    print("test_get_symbols_polygon")
    config.data_connector = DataConnectorType.polygon
    dl = DataLoader(TimeScale.minute)
    tickers = dl.data_api.get_symbols()
    print(len(tickers))

    return True


@pytest.mark.devtest
def test_apple_update() -> bool:
    print("test_apple_stock_price_open_str")
    dl = DataLoader(TimeScale.minute)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["AAPL"][-1]
    print("after this")
    dl["AAPL"].loc["2021-02-02 09:46:00"] = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]
    print(dl["AAPL"].loc["2021-02-02 09:46:00"])

    return True
