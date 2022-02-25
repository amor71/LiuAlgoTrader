import math
import os
import time
from datetime import date, datetime, timedelta
from typing import Awaitable, Callable, Dict, List, Optional, Tuple

import pandas as pd
import pandas_market_calendars
import pytz
import requests
import websocket

from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.data.data_base import DataAPI

NY = "America/New_York"
nytz = pytz.timezone(NY)


class TradierData(DataAPI):
    tradier_account_number: Optional[str] = os.getenv("TRADIER_ACCOUNT_NUMBER")
    tradier_access_token: Optional[str] = os.getenv("TRADIER_ACCESS_TOKEN")
    base_url = "https://sandbox.tradier.com/v1/"
    base_websocket = "https://stream.tradier.com/v1/"
    datapoints_per_request = 500
    max_trades_per_minute = 10

    def __init__(self):
        ...

    def _get(self, url: str, params: Dict):
        print(params)
        r = requests.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {self.tradier_access_token}",
                "Accept": "application/json",
            },
        )

        if r.status_code in (429, 502):
            tlog(f"{url} return {r.status_code}, waiting and re-trying")
            time.sleep(10)
            return self._get(url, params)

        return r

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        print(symbol, start, end, scale)
        if scale == TimeScale.day:
            url = f"{self.base_url}/markets/history"
            interval = "daily"
            s = str(start)
            e = str(end)
        elif scale == TimeScale.minute:
            url = f"{self.base_url}/markets/timesales"
            interval = "1min"
            s = datetime.combine(start, datetime.min.time()).strftime(
                "%Y-%m-%d %H:%M"
            )
            e = datetime.combine(end, datetime.max.time()).strftime(
                "%Y-%m-%d %H:%M"
            )
        else:
            raise NotImplementedError(f"scale {scale} not implemented yet")

        response = self._get(
            url,
            params={
                "symbol": symbol,
                "interval": interval,
                "start": s,
                "end": e,
            },
        )

        if response.status_code != 200:
            raise ValueError(
                f"HTTP ERROR {response.status_code} {response.text}"
            )

        if scale == TimeScale.day:
            data = response.json()["history"]["day"]
            df = pd.DataFrame(data=data)

            df.date = pd.to_datetime(df.date).dt.tz_localize("EST")
            df.set_index(
                "date", drop=True, inplace=True, verify_integrity=True
            )
            df["count"] = 0
            df["average"] = 0.0
            df["vwap"] = 0.0
        elif scale == TimeScale.minute:
            data = response.json()["series"]["data"]
            df = pd.DataFrame.from_records(data)
            df.time = pd.to_datetime(df.time).dt.tz_localize("EST")
            df.set_index(
                "time", drop=True, inplace=True, verify_integrity=True
            )
            df.drop(["timestamp"], axis=1, inplace=True)
            df["count"] = 0
            df = df.rename(columns={"price": "average"})

        print(df)
        return df

    def get_market_snapshot(
        self, filter_func: Optional[Callable]
    ) -> List[Dict]:
        raise NotImplementedError("get_market_snapshot")

    def get_symbols(self) -> List[str]:
        raise NotImplementedError("get_symbols")

    def get_symbols_data(
        self,
        symbols: List[str],
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> Dict[str, pd.DataFrame]:
        ...

    def get_last_trading(self, symbol: str) -> datetime:
        url = f"{self.base_url}/markets/quotes"
        response = self._get(
            url,
            params={
                "symbols": [symbol],
            },
        )
        if response.status_code == 200:
            data = response.json()
            if "quotes" in data and "quote" in data["quotes"]:
                return (
                    pd.Timestamp(
                        data["quotes"]["quote"]["trade_date"], unit="ms"
                    )
                    .tz_localize("UTC")
                    .tz_convert("EST")
                )

        raise ValueError(f"get_last_trading({symbol}) failed w {response}")

    def get_trading_holidays(self) -> List[str]:
        nyse = pandas_market_calendars.get_calendar("NYSE")
        return nyse.holidays().holidays

    def get_trading_day(
        self, symbol: str, now: datetime, offset: int
    ) -> datetime:
        cbd_offset = pd.tseries.offsets.CustomBusinessDay(
            n=offset, holidays=self.get_trading_holidays()
        )

        return nytz.localize(now + cbd_offset)

    def trading_days_slice(self, symbol: str, slice) -> slice:
        raise NotImplementedError("trading_days_slice")

    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_minutes")

    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_days")

    def get_max_data_points_per_load(self) -> int:
        raise NotImplementedError("get_max_data_points_per_load")
