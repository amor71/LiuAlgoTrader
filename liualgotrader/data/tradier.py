import time as time_action
from datetime import date, datetime, time
from typing import Callable, Dict, List, Optional

import pandas as pd
import pandas_market_calendars
import pytz
import requests

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.data.data_base import DataAPI

NY = "America/New_York"
nytz = pytz.timezone(NY)


class TradierData(DataAPI):
    datapoints_per_request = 500
    max_trades_per_minute = 10

    def __init__(self):
        ...

    def _get(self, url: str, params: Dict = None):
        if params is None:
            params = {}
        r = requests.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {config.tradier_access_token}",
                "Accept": "application/json",
            },
        )
        if r.status_code in (429, 502):
            tlog(f"{url} return {r.status_code}, waiting and re-trying")
            time_action.sleep(10)
            return self._get(url, params)

        return r

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        if scale == TimeScale.day:
            url = f"{config.tradier_base_url}markets/history"
            interval = "daily"
            s = str(start)
            e = str(end)
        elif scale == TimeScale.minute:
            url = f"{config.tradier_base_url}markets/timesales"
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

        df: pd.DataFrame = pd.DataFrame()
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
            data = response.json()

            try:
                if data and data["series"]:
                    data = data["series"]["data"]
                    df = pd.DataFrame.from_records(data)
                    df.time = pd.to_datetime(df.time).dt.tz_localize("EST")
                    df.set_index(
                        "time", drop=True, inplace=True, verify_integrity=True
                    )
                    df.drop(["timestamp"], axis=1, inplace=True)
                    df["count"] = 0
                    df = df.rename(columns={"price": "average"}).between_time(
                        "04:00", "19:59"
                    )
            except Exception as exc:
                raise ValueError(f"data={data}") from exc

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

    def _get_previous_month_last_trading(
        self, month: int, year: int
    ) -> datetime:
        url = f"{config.tradier_base_url}markets/calendar"
        response = self._get(url, params={"month": month})
        data = response.json()
        return self._get_previous_last_trading(
            data, len(data["calendar"]["days"]["day"]) - 1, month, year
        )

    def _get_previous_last_trading(
        self, data: Dict, index: int, month: int, year: int
    ) -> datetime:
        if index > 0:
            if data["calendar"]["days"]["day"][index - 1]["status"] == "open":
                date_str = data["calendar"]["days"]["day"][index - 1]["date"]
                day = datetime.strptime(date_str, "%Y-%m-%d").date()
                return nytz.localize(datetime.combine(day, time(hour=20)))
            return self._get_previous_last_trading(
                data, index - 1, month, year
            )
        return (
            self._get_previous_month_last_trading(month=month - 1, year=year)
            if month > 0
            else self._get_previous_month_last_trading(month=12, year=year - 1)
        )

    def get_last_trading(self, symbol: str) -> datetime:
        url = f"{config.tradier_base_url}markets/calendar"
        response = self._get(
            url,
        )
        data = response.json()
        today = datetime.now(nytz).date()
        for i, day in enumerate(data["calendar"]["days"]["day"]):
            if day["date"] == str(today):
                if day["status"] == "open":
                    return datetime.now(tz=nytz)

                return self._get_previous_last_trading(
                    data, i, today.month, today.year
                )
            i += 1

        raise AssertionError(
            f"Could not find {today} in current trading month"
        )

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

    def trading_days_slice(self, symbol: str, time_slice) -> slice:
        raise NotImplementedError("trading_days_slice")

    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_minutes")

    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_days")

    def get_max_data_points_per_load(self) -> int:
        raise NotImplementedError("get_max_data_points_per_load")
