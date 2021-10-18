from datetime import date, datetime

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale


@pytest.mark.devtest
def test_create_data_loader_default() -> bool:
    return bool(DataLoader(connector=DataConnectorType.gemini))


@pytest.mark.devtest
def test_stock_current_price() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price = dl["BTCUSD"].close[-1]
    last_price_time = dl["BTCUSD"].close.index[-1]
    before_price = dl["BTCUSD"].close[-5]
    before_price_time = dl["BTCUSD"].close.index[-5]

    print(
        f"BTCUSD {last_price} @ {last_price_time}, before was {before_price}@{before_price_time}"
    )

    return True


@pytest.mark.devtest
def test_stock_current_price_range_int_minute() -> bool:
    print("test_stock_current_price_range_int_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].close[-5:-1]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_stock_current_price_range_int_day() -> bool:
    print("test_stock_current_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"].close[-6:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_daily_price() -> bool:
    print("test_stock_daily_price")
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.gemini)
    last_price = dl["ETHUSD"].close[-1]
    last_price_time = dl["ETHUSD"].close.index[-1]
    print(last_price, last_price_time)
    before_price = dl["ETHUSD"].close[-5]
    before_price_time = dl["ETHUSD"].close.index[-5]
    print(
        f"ETHUSD {last_price} @ {last_price_time}, before was {before_price}@{before_price_time}"
    )

    return True


@pytest.mark.devtest
def test_negative_current_price() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    try:
        dl["DFGDFGDFG"].close[-1]
    except ValueError:
        return True

    return False


@pytest.mark.devtest
def test_stock_close_price_range_str_day() -> bool:
    print("test_stock_close_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].close[
        "2021-10-01":"2021-10-05"  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_close_price_range_str_minute() -> bool:
    print("test_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["UTCBSD"].close[
        "2021-09-05 09:45:00":"2021-09-05 09:50:00"  # type:ignore
    ]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_close_price_range_str_minute_int() -> bool:
    print("test_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["UTCBSD"].close[
        "2021-09-05 09:45:00":-1  # type:ignore
    ]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_range_int_minute() -> bool:
    print("test_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHBSD"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_range_int_day() -> bool:
    print("test_stock_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHBSD"][-5:-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_range_date_day() -> bool:
    print("test_stock_price_range_date_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHBSD"]["2020-10-05":"2020-10-08"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_stock_price_range_date_int_day() -> bool:
    print("test_stock_price_range_date_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"]["2021-10-05":-1]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_apple_price_range_date_int_min() -> bool:
    print("test_stock_price_range_date_int_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"]["2021-10-05":-1]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_stock_price_range_date_int_min_open() -> bool:
    print("test_stock_price_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"]["2021-10-05":]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_stock_price_open_range_date_int_min_open() -> bool:
    print("test_stock_price_close_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].open["2021-10-05":]  # type:ignore
    print(last_price_range)
    return True


@pytest.mark.devtest
def test_stock_price_range_date_min_open() -> bool:
    print("test_stock_price_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    try:
        last_price_range = dl["ETHUSD"][:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_stock_price_open_range_date_min_open() -> bool:
    print("test_stock_price_open_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    try:
        last_price_range = dl["UTCBSD"].open[:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return True
    return True


@pytest.mark.devtest
def test_stock_price_range_date_min() -> bool:
    print("test_stock_price_range_date_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=9, day=1)
    d2 = date(year=2021, month=9, day=2)
    last_price_range = dl["UTCBSD"][d1:d2].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_range_date_min_mixed() -> bool:
    print("test_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=9, day=1)
    last_price_range = dl["ETHUSD"][
        d1:"2021-10-02"  # type:ignore
    ].between_time(  # type:ignore
        "9:30", "16:00"  # type:ignore
    )  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_range_date_day_mixed() -> bool:
    print("test_stock_price_range_date_day_mixed")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=9, day=1)
    last_price_range = dl["BTCUSD"][d1:"2021-10-02"]  # type:ignore
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_open_range_date_min_mixed() -> bool:
    print("test_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=9, day=1)
    last_price_range = (
        dl["ETHUSD"]
        .open[d1:"2021-09-01"]  # type:ignore
        .between_time("9:30", "16:00")  # type:ignore
    )
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_open_str() -> bool:
    print("test_stock_price_open_str")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=9, day=1)
    last_price_range = dl["BTCUSD"].open["2021-09-02 09:45:00"]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_stock_price_open_date() -> bool:
    print("test_stock_price_open_date")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=9, day=1)
    last_price_range = dl["BTCUSD"].open[d1]
    print(last_price_range)

    return True


@pytest.mark.devtest
def test_get_symbols_alpaca() -> bool:
    print("test_get_symbols_gemini")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    tickers = dl.data_api.get_symbols()
    print(len(tickers))

    return True


@pytest.mark.devtest
def test_apple_update() -> bool:
    print("test_stock_price_open_str")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date(year=2021, month=2, day=1)
    last_price_range = dl["BTCUSD"][-1]
    print("after this")
    dl["BTCUSD"].loc["2021-09-02 09:46:00"] = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]
    print(dl["BTCUSD"].loc["2021-09-02 09:46:00"])

    return True
