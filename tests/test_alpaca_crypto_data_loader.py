from datetime import date, datetime

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

    data = dl["ETHUSD"]["2021-05-01":"2021-10-01"]  # type: ignore
    print(data)
    return True
