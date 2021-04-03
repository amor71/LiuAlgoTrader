import asyncio
import json
import queue
import traceback
from datetime import date, datetime, timedelta
from multiprocessing import Queue
from typing import Awaitable, Dict, List, Optional

import pandas as pd
import pytz
import requests
from finnhub import Client

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import (QueueMapper, TimeScale, WSConnectState,
                                        WSEventType)
from liualgotrader.data import static
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI

NY = "America/New_York"
nytz = pytz.timezone(NY)


def check_auth(f):
    def wrapper(*args):
        if not args[0].finnhub_rest_client:
            raise AssertionError("Must call w/ authenticated Finnhub client")
        return f(*args)

    return wrapper


class FinnhubData(DataAPI):
    def __init__(self):
        self.finnhub_rest_client = Client(api_key=config.finnhub_api_key)
        if not self.finnhub_rest_client:
            raise AssertionError("Failed to authenticate Finnhub  client")

        self.stock_exchanges = pd.read_csv(static.finnhub_exchanges_url)

    @check_auth
    def get_symbols(
        self, country: str = "", exchange: str = None
    ) -> List[Dict]:
        exchanges = ""
        return self.finnhub_rest_client.stock_symbols(exchange=exchanges)

    @check_auth
    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        _start = nytz.localize(
            datetime.combine(start, datetime.min.time())
        ).timestamp()
        _end = nytz.localize(
            datetime.now().replace(microsecond=0) - timedelta(days=1)
        ).timestamp()
        t: Optional[str] = (
            "1"
            if scale == TimeScale.minute
            else "D"
            if scale == TimeScale.day
            else None
        )

        if not t:
            raise AssertionError(
                f"timescale {scale} not support in Finnhub implementation"
            )
        data = pd.DataFrame(
            self.finnhub_rest_client.stock_candles(
                symbol,
                t,
                _start,
                _end,
            )
        )
        if data.empty:
            raise ValueError(
                f"[ERROR] {symbol} has no data for {_start} to {_end} w {scale.name}"
            )

        return data
