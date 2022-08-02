from datetime import date, timedelta

import pandas as pd
import pytest
from alpaca_trade_api.rest import TimeFrame
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale
from liualgotrader.data.alpaca import AlpacaData, AlpacaStream

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_crypto_get_symbol() -> bool:
    alpaca_data = AlpacaData()

    start = date(2021, 5, 1)
    end = date(2021, 10, 1)
    _start, _end = alpaca_data._localize_start_end(start, end)
    df = alpaca_data.crypto_get_symbol_data(
        symbol="BTCUSD", start=_start, end=_end, timeframe=TimeFrame.Day
    )
    print(df)
    return True


@pytest.mark.devtest
def test_btc_data_loader_day() -> bool:
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    data = dl["BTCUSD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)
    return True


@pytest.mark.devtest
def test_btc_data_loader_min() -> bool:
    dl = DataLoader(connector=DataConnectorType.alpaca)

    data = dl["BTCUSD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)
    return True


@pytest.mark.devtest
def test_eth_data_loader_day() -> bool:
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    data = dl["ETH/USD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)
    return True


@pytest.mark.devtest
def test_eth_data_loader_minute_offset() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    data = dl["ETH/USD"][-1500:]  # type: ignore
    print(len(data), data)
    return True


@pytest.mark.devtest
def test_eth_data_loader_length() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    end = pd.to_datetime("2022-07-28 21:20:00-04:00")
    print("end:", end)
    data = dl["ETH/USD"][end + timedelta(minutes=-1500) : end]  # type: ignore

    if len(data) != 1499:
        raise AssertionError(f"Data length {len(data)} is not 1500")

    print(len(data), data)
    return True


@pytest.mark.devtest
def test_eth_data_loader_length2() -> bool:
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    end = pd.to_datetime("2022-07-28 21:20:00-04:00")
    print("end:", end)

    data = dl["ETH/USD"][end + timedelta(minutes=-2000) : end + timedelta(minutes=-100)]  # type: ignore

    data = dl["ETH/USD"][end + timedelta(minutes=-1500) : end]  # type: ignore

    if len(data) != 1499:
        raise AssertionError(f"Data length {len(data)} is not 1500")

    print(len(data), data)
    return True


@pytest.mark.devtest
def test_eth_data_loader_day_offset() -> bool:
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    data = dl["ETH/USD"][-1500:]  # type: ignore
    print(len(data), data)
    return True
