import math
from abc import ABCMeta, abstractmethod
from datetime import date, datetime
from typing import Awaitable, Callable, Dict, List, Optional

import pandas as pd

from liualgotrader.common.types import TimeScale


class DataAPI(metaclass=ABCMeta):
    def __init__(self, ws_uri: str, ws_messages_handler: Awaitable):
        self.ws_uri = ws_uri
        self.ws_msgs_handler = ws_messages_handler

    @abstractmethod
    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_market_snapshot(
        self, filter_func: Optional[Callable]
    ) -> List[Dict]:
        ...

    @abstractmethod
    def get_symbols(self) -> List[str]:
        ...

    @abstractmethod
    def get_symbols_data(
        self,
        symbols: List[str],
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> Dict[str, pd.DataFrame]:
        ...

    @abstractmethod
    def get_last_trading(self, symbol: str) -> datetime:
        ...

    @abstractmethod
    def get_trading_day(
        self, symbol: str, now: datetime, offset: int
    ) -> datetime:
        ...

    @abstractmethod
    def trading_days_slice(self, symbol: str, slice) -> slice:
        ...

    @abstractmethod
    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        ...

    @abstractmethod
    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        ...

    @abstractmethod
    def get_max_data_points_per_load(self) -> int:
        ...

    def data_concurrency_ranges(
        self, symbol: str, start: date, end: date, scale: TimeScale
    ) -> List[Optional[pd.DatetimeIndex]]:
        scale_factor_minutes = self.num_trading_minutes(symbol, start, end)
        data_points = (
            scale_factor_minutes / 60
            if scale == TimeScale.day
            else scale_factor_minutes
        )
        total_data_points = (
            self.num_trading_days(symbol, start, end) * data_points
        )
        periods = math.ceil(
            total_data_points / self.get_max_data_points_per_load()
        )
        return pd.date_range(start, end, periods=periods + 1)
