import asyncio
import os
import queue
import traceback
from datetime import date, datetime, timedelta
from random import randint
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import pytz
import requests

from liualgotrader.common import config
from liualgotrader.common.list_utils import chunks
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper, TimeScale, WSEventType
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI

utctz = pytz.timezone("UTC")


class GeminiData(DataAPI):
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_api_secret: Optional[str] = os.getenv("GEMINI_API_SECRET")
    base_url = "https://api.sandbox.gemini.com"
    base_websocket = "wss://api.sandbox.gemini.com"

    def __init__(self):
        self.running_task: Optional[Thread] = None
        self.ws = None

    def get_symbols(self) -> List[Dict]:
        endpoint = "/v1/symbols"
        url = self.base_url + endpoint
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        print(symbol, start, end, scale)
        start_ts, end_ts = (
            int(datetime.combine(start, datetime.min.time()).timestamp()),
            int(datetime.combine(end, datetime.min.time()).timestamp()),
        )

        current_timestamp = start_ts
        endpoint = f"/v1/trades/{symbol}"
        start = datetime(1970, 1, 1, tzinfo=utctz)  # Unix epoch start time
        returned_df: pd.DataFrame = pd.DataFrame()
        while current_timestamp < end_ts:
            url = f"{self.base_url}{endpoint}?since={current_timestamp}&limit_trades=500"
            response = requests.get(url)
            if response.status_code != 200:
                raise AssertionError(
                    f"[EXCEPTION] GEMINI get_symbol_data {symbol} {current_timestamp} : {response.status_code} {response.text}"
                )

            _df = pd.DataFrame(response.json())

            current_timestamp = _df.timestamp.astype(int).max()
            _df["ms"] = _df.timestampms.apply(
                lambda x: start + timedelta(milliseconds=x)
            )
            _df["amount"] = pd.to_numeric(_df.amount)
            _df = _df[["ms", "price", "amount"]].set_index("ms")
            rule = "T" if scale == TimeScale.minute else "D"
            _newdf = _df.resample(rule).first()
            _newdf["high"] = _df.resample(rule).max().price
            _newdf["low"] = _df.resample(rule).min().price
            _newdf["close"] = _df.resample(rule).last().price
            _newdf["count"] = _df.resample(rule).count().amount
            _newdf["volume"] = _df.resample(rule).sum().amount
            _newdf = (
                _newdf.rename(columns={"price": "open", "ms": "timestamp"})
                .drop(columns=["amount"])
                .sort_index()
            )
            _newdf = _newdf.dropna()
            _newdf["average"] = 0.0
            _newdf["vwap"] = 0.0

            if returned_df.empty:
                returned_df = _newdf
            else:
                returned_df = pd.concat([returned_df, _newdf])
                returned_df = returned_df[
                    ~returned_df.index.duplicated(keep="first")
                ]

        return returned_df
