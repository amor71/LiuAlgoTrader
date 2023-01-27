from datetime import timedelta

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_btc_data_loader_day():
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    data = dl["BTC/USD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)


@pytest.mark.devtest
def test_btc_data_loader_min():
    dl = DataLoader(connector=DataConnectorType.alpaca)

    data = dl["BTC/USD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)


@pytest.mark.devtest
def test_eth_data_loader_day():
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    data = dl["ETH/USD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)


@pytest.mark.devtest
def test_eth_data_loader_minute_offset():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    data = dl["ETH/USD"][-1500:]  # type: ignore
    print(len(data), data)


@pytest.mark.devtest
def test_eth_data_loader_length():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    end = pd.to_datetime("2022-07-28 21:20:00-04:00")
    print("end:", end)
    data = dl["ETH/USD"][end + timedelta(minutes=-1500) : end]  # type: ignore

    print(data, len(data))

    if len(data) != 1498:
        raise AssertionError(f"Data length {len(data)} is not 1498")


@pytest.mark.devtest
def test_eth_data_loader_day_offset():
    dl = DataLoader(TimeScale.day, connector=DataConnectorType.alpaca)

    data = dl["ETH/USD"][-1500:]  # type: ignore
    print(len(data), data)
