import io
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import pytz
import requests
from finnhub import Client

from liualgotrader.common import config
from liualgotrader.common.types import TimeScale
from liualgotrader.data import static
from liualgotrader.data.data_base import DataAPI

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

        s = requests.get(static.finnhub_exchanges_url).content
        self.stock_exchanges: pd.DataFrame = pd.read_csv(
            io.StringIO(s.decode("utf-8"))
        )

    @check_auth
    def get_symbols(
        self,
        country: str = "US",
    ) -> List[Dict]:
        if country not in self.stock_exchanges.code.to_list():
            raise AssertionError(
                f"country code {country} not supported, valid values are {self.stock_exchanges.code.to_list()}"
            )
        return self.finnhub_rest_client.stock_symbols(exchange=country)

    # @check_auth
    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        _start = int(datetime.combine(start, datetime.min.time()).timestamp())
        _end = int(
            datetime.combine(
                end if scale == TimeScale.day else end + timedelta(days=1),
                datetime.min.time(),
            ).timestamp()
        )
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
        data.t = pd.to_datetime(data.t, unit="s")
        data = data.set_index(data.t)
        data = data.tz_localize("America/New_York", ambiguous="infer")
        data = data[data.s == "ok"]
        data = data.drop(columns=["s", "t"])
        data.rename(
            columns={
                "o": "open",
                "c": "close",
                "h": "high",
                "l": "low",
                "v": "volume",
            },
            inplace=True,
        )

        if data.empty:
            raise ValueError(
                f"[ERROR] {symbol} has no data for {_start} to {_end} w {scale.name}"
            )

        return data
