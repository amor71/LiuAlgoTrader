import asyncio
import concurrent.futures
import time
from datetime import date, datetime, timedelta

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


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.mark.devtest
def test_apple_stock_range() -> bool:
    print("+ test_apple_stock_range()")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    start_time = time.time()
    data = dl["AAPL"]["2021-01-01":"2021-10-01"]  # type: ignore
    print(f"1st load_time: {time.time()-start_time}")

    start_time = time.time()
    data = dl["AAPL"]["2021-01-01":"2021-10-01"]  # type: ignore
    print(f"2nd load_time: {time.time()-start_time}")

    print("- test_apple_stock_range()")

    return True


@pytest.mark.devtest
def test_apple_stock_range2() -> bool:
    print("+ test_apple_stock_range2()")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    start_time = time.time()
    now = datetime.now(nyc)
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]
    print(f"1st load_time: {time.time()-start_time}")

    start_time = time.time()
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]  # type: ignore
    print(f"2nd load_time: {time.time()-start_time}")

    print("- test_apple_stock_range2()")

    return True


@pytest.mark.devtest
def test_apple_stock_range3() -> bool:
    print("+ test_apple_stock_range3()")
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)

    start_time = time.time()
    now = datetime.now(nyc)
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]
    print(f"1st load_time: {time.time()-start_time}")

    start_time = time.time()
    now = datetime.now(nyc)
    data = dl["AAPL"][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]  # type: ignore
    print(f"2nd load_time: {time.time()-start_time}")

    print("- test_apple_stock_range3()")

    return True


def load_data_for_symbol(data_loader: DataLoader, symbol: str, now: datetime):
    start_time = time.time()

    data = data_loader[symbol][
        now.date() - timedelta(days=int(100 * 7 / 5)) : now.replace(hour=9, minute=30, second=0, microsecond=0)  # type: ignore
    ]
    return time.time() - start_time


@pytest.mark.devtest
def test_apple_stock_range4() -> bool:
    print("+ test_apple_stock_range4()")
    now = datetime.now(nyc)
    dl = DataLoader(TimeScale.minute, connector=DataConnectorType.alpaca)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Start the load operations and mark each future with its URL
        futures = {
            executor.submit(load_data_for_symbol, dl, symbol, now): symbol
            for symbol in ["AAPL"]
        }
        for future in concurrent.futures.as_completed(futures):
            print(f"time-passed1 {future.result()}")
    now = datetime.now(nyc)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Start the load operations and mark each future with its URL
        futures = {
            executor.submit(load_data_for_symbol, dl, symbol, now): symbol
            for symbol in ["AAPL"]
        }
        for future in concurrent.futures.as_completed(futures):
            print(f"time-passed2 {future.result()}")

    print("- test_apple_stock_range4()")

    return True
