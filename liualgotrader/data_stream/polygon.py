import time
from datetime import date
from typing import Awaitable, List

import pandas as pd
from polygon import RESTClient

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale, WSEventType
from liualgotrader.data_stream.base import DataAPI


class Polygon(DataAPI):
    def __init__(self):
        self.polygon_rest_client = RESTClient(config.polygon_api_key)
        if not self.polygon_rest_client:
            raise AssertionError(
                "Failed to authenticate Polygon restful client"
            )

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        if not self.polygon_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")

        retry = True
        i = 5

        data = self.polygon_rest_client.stocks_equities_aggregates(
            symbol, 1, scale.name, start, end, unadjusted=False
        )
        if not data or not hasattr(data, "results"):
            raise ValueError(
                f"[ERROR] {symbol} has no data for {start} to {end} w {scale.name}"
            )

        d = {}
        for result in data.results:
            d[pd.Timestamp(result["t"], unit="ms", tz="America/New_York")] = [
                result.get("o"),
                result.get("h"),
                result.get("l"),
                result.get("c"),
                result.get("v"),
                result.get("vw"),
                result.get("n"),
            ]

        _df = pd.DataFrame.from_dict(
            d,
            orient="index",
            columns=[
                "open",
                "high",
                "low",
                "close",
                "volume",
                "average",
                "count",
            ],
        )
        return _df

    async def connect(self) -> bool:
        return False

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        return False

    async def unsubscribe(self, symbols: List[str]) -> bool:
        return True
