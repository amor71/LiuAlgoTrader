from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale


@pytest.mark.devtest
def test_create_data_loader_default():
    DataLoader(connector=DataConnectorType.gemini)


@pytest.mark.devtest
def test_ethusd_stock_daily_price():
    print("test_ethusd_stock_daily_price")
    dl = DataLoader(scale=TimeScale.day, connector=DataConnectorType.gemini)
    last_price = dl["ETHUSD"].close[-1]

    last_price_time = dl["ETHUSD"].close.index[-1]
    print(last_price, last_price_time)
    before_price = dl["ETHUSD"].close[-10]

    print(dl["ETHUSD"])
    print(
        f"ETH/USD {last_price} @ {last_price_time}, before was {before_price}"
    )


@pytest.mark.devtest
def test_btc_current_price():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price = dl["BTCUSD"].close[-1]
    last_price_time = dl["BTCUSD"].close.index[-1]
    before_price = dl["BTCUSD"].close[-5]
    before_price_time = dl["BTCUSD"].close.index[-5]

    print(
        f"BTCUSD {last_price} @ {last_price_time}, before was {before_price}@{before_price_time}"
    )


@pytest.mark.devtest
def test_stock_current_price_range_int_minute():
    print("test_stock_current_price_range_int_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].close[-5:-1]  # type:ignore
    print(last_price_range)


@pytest.mark.devtest
def test_negative_current_price():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    try:
        dl["DFGDFGDFG"].close[-1]
    except ValueError:
        return


@pytest.mark.devtest
def test_stock_close_price_range_str_day():
    print("test_stock_close_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].close[
        str(date.today() - timedelta(days=20)) : str(  # type:ignore
            date.today() - timedelta(days=10)
        )  # type:ignore
    ]
    print(last_price_range)


@pytest.mark.devtest
def test_apple_close_price_range_str_minute():
    print("test_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].close[
        str(  # type: ignore
            (datetime.now() - timedelta(days=20)).replace(hour=10, minute=5)
        ) : str(  # type:ignore
            (datetime.now() - timedelta(days=20)).replace(hour=10, minute=5)
        )
    ]

    print(last_price_range)


@pytest.mark.devtest
def test_stock_close_price_range_str_minute_int():
    print("test_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].close[
        str((datetime.now() - timedelta(days=2)).replace(hour=10, minute=5)) : -1  # type: ignore
    ]

    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_int_minute():
    print("test_stock_close_price_range_str_minute")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"][-5:-1]  # type:ignore
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_int_day():
    print("test_stock_price_range_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"][-5:-1]  # type:ignore
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_day():
    print("test_stock_price_range_date_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"][
        str(date.today() - timedelta(days=20)) : str(  # type:ignore
            date.today() - timedelta(days=10)  # type:ignore
        )
    ]
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_int_day():
    print("test_stock_price_range_date_int_day")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"][
        str(date.today() - timedelta(days=10)) : -1  # type:ignore
    ]
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_int_min():
    print("test_stock_price_range_date_int_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["ETHUSD"][
        (datetime.now(timezone.utc) - timedelta(days=2)).replace(
            hour=10, minute=5
        ) : -1  # type:ignore
    ]  # type:ignore
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_int_min_open():
    print("test_stock_price_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"][
        str(date.today() - timedelta(days=10)) :  # type:ignore
    ]
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_open_range_date_int_min_open():
    print("test_stock_price_close_range_date_int_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    last_price_range = dl["BTCUSD"].open[
        str(date.today() - timedelta(days=10)) :  # type:ignore
    ]
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_min_open():
    print("test_stock_price_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    try:
        last_price_range = dl["ETHUSD"][:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return


@pytest.mark.devtest
def test_stock_price_open_range_date_min_open():
    print("test_stock_price_open_range_date_min_open")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    try:
        last_price_range = dl["BTCUSD"].open[:]  # type:ignore
        print(last_price_range)
    except ValueError:
        return


@pytest.mark.devtest
def test_stock_price_range_date_min():
    print("test_stock_price_range_date_min")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date.today() - timedelta(days=10)
    d2 = date.today() - timedelta(days=9)
    last_price_range = dl["BTCUSD"][d1:d2].between_time(  # type:ignore
        "9:30", "16:00"
    )  # type:ignore
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_min_mixed():
    print("test_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date.today() - timedelta(days=20)
    last_price_range = dl["ETHUSD"][
        d1 : str(date.today() - timedelta(days=10))  # type:ignore
    ].between_time(  # type:ignore
        "9:30", "16:00"  # type:ignore
    )  # type:ignore
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_range_date_day_mixed():
    print("test_stock_price_range_date_day_mixed")
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.gemini)

    d1 = date.today() - timedelta(days=20)
    last_price_range = dl["BTCUSD"][
        d1 : date.today()  # type:ignore
    ]
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_open_range_date_min_mixed():
    print("test_stock_price_range_date_min_mixed")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date.today() - timedelta(days=20)
    last_price_range = (
        dl["ETHUSD"]
        .open[d1 : str(date.today() - timedelta(days=10))]  # type:ignore
        .between_time("9:30", "16:00")  # type:ignore
    )
    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_open_str():
    print("test_stock_price_open_str")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date.today() - timedelta(days=20)
    last_price_range = dl["BTCUSD"].open[
        str((datetime.now() - timedelta(days=20)).replace(hour=10, minute=5))
    ]

    print(last_price_range)


@pytest.mark.devtest
def test_stock_price_open_date():
    print("test_stock_price_open_date")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date.today() - timedelta(days=20)
    last_price_range = dl["BTCUSD"].open[d1]
    print(last_price_range)


@pytest.mark.devtest
def test_get_symbols_alpaca():
    print("test_get_symbols_gemini")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    tickers = dl.data_api.get_symbols()
    print(len(tickers))


@pytest.mark.devtest
def test_stock_price_open_str2():
    print("test_stock_price_open_str2")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.gemini)
    d1 = date.today() - timedelta(days=20)
    dl["BTCUSD"][-1]
    print("after this")
    dl["BTCUSD"].loc[
        str(
            (datetime.now() - timedelta(days=20)).replace(
                hour=10, minute=5, microsecond=0
            )
        )
    ] = [
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
        100.0,
    ]

    print(
        dl["BTCUSD"].loc[
            str(
                (datetime.now() - timedelta(days=20)).replace(
                    hour=10, minute=5, microsecond=0
                )
            )
        ]
    )
