import asyncio
import concurrent.futures
import time
from datetime import datetime, timedelta

import pandas as pd
import pytest
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.types import DataConnectorType, TimeScale

nyc = timezone("America/New_York")


@pytest.mark.devtest
def test_create_data_loader_default():
    DataLoader(connector=DataConnectorType.alpaca)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.mark.devtest
def test_apple_stock_range():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    start_time = time.time()
    data = dl["AAPL"]["2021-01-01":"2021-10-01"]  # type: ignore
    duration_first = time.time() - start_time
    print(f"1st load time: {duration_first}")

    start_time = time.time()
    data = dl["AAPL"]["2021-01-01":"2021-10-01"]  # type: ignore
    duration_second = time.time() - start_time
    print(f"2nd load_time: {duration_second}")

    assert (
        duration_second < duration_first * 10
    ), f"expected {duration_second} < {duration_first} * 10"


@pytest.mark.devtest
def test_apple_stock_range2():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    start_time = time.time()
    now = datetime.now(nyc)
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]
    first_load_time = time.time() - start_time
    print(f"1st load_time: {first_load_time}")

    start_time = time.time()
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]  # type: ignore
    second_load_time = time.time() - start_time
    print(f"2nd load_time: {second_load_time}")

    assert (
        second_load_time < first_load_time * 10
    ), f"expected {second_load_time} < {first_load_time} * 10"


@pytest.mark.devtest
def test_apple_stock_range3():
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    start_time = time.time()
    now = datetime.now(nyc)
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]
    first_load_time = time.time() - start_time
    print(f"1st load_time: {first_load_time}")

    start_time = time.time()
    now = datetime.now(nyc)
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]  # type: ignore
    second_load_time = time.time() - start_time
    print(f"2nd load_time: {second_load_time}")

    assert (
        second_load_time < first_load_time * 10
    ), f"expected {second_load_time} < {first_load_time} * 10"


def load_data_for_symbol(data_loader: DataLoader, symbol: str, now: datetime):
    time.time()

    return data_loader[symbol][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]


@pytest.mark.devtest
def test_apple_stock_range4():
    now = datetime.now(nyc)
    t0 = time.time()
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Start the load operations and mark each future with its URL
        futures = {
            executor.submit(load_data_for_symbol, dl, symbol, now): symbol
            for symbol in ["AAPL"]
        }
        for future in concurrent.futures.as_completed(futures):
            print(f"time-passed1 {future.result()}")

    first_load_time = time.time() - t0
    print(f"first load time is {first_load_time} seconds")

    now = datetime.now(nyc)
    t0 = time.time()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Start the load operations and mark each future with its URL
        futures = {
            executor.submit(load_data_for_symbol, dl, symbol, now): symbol
            for symbol in ["AAPL"]
        }
        for future in concurrent.futures.as_completed(futures):
            print(f"time-passed2 {future.result()}")

    second_load_time = time.time() - t0
    print(f"second load time is {second_load_time} seconds")
    assert (
        second_load_time < first_load_time * 10
    ), f"expected {second_load_time} < {first_load_time} * 10"
