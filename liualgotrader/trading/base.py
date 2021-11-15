import asyncio
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
from math import ceil

from liualgotrader.common.types import Order, QueueMapper
from liualgotrader.models.algo_run import AlgoRun
from liualgotrader.data.alpaca import get_scale_factor
from liualgotrader.common.types import TimeScale


class Trader:
    __instance: object = None

    def __init__(self, queues: QueueMapper = None):
        self.queues = queues
        Trader.__instance = self

    def __repr__(self):
        return type(self).__name__

    async def create_session(self, algo_name: str) -> AlgoRun:
        new_batch_id = str(uuid.uuid4())
        algo_run = AlgoRun(algo_name, new_batch_id)
        await algo_run.save()
        return algo_run

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        ...

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        ...

    def is_market_open_today(self) -> bool:
        ...

    def get_time_market_close(self) -> Optional[timedelta]:
        ...

    def get_position(self, symbol: str) -> float:
        ...

    async def reconnect(self):
        ...

    async def get_tradeable_symbols(self) -> List[str]:
        ...

    async def get_shortable_symbols(self) -> List[str]:
        ...

    async def is_shortable(self, symbol: str) -> bool:
        ...

    async def is_order_completed(self, order: Order) -> Tuple[bool, float]:
        ...

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str,
        time_in_force: str,
        limit_price: str = None,
        stop_price: str = None,
        client_order_id: str = None,
        extended_hours: bool = None,
        order_class: str = None,
        take_profit: dict = None,
        stop_loss: dict = None,
        trail_price: str = None,
        trail_percent: str = None,
    ) -> Order:
        ...

    async def get_order(self, order_id: str) -> Order:
        ...

    async def cancel_order(
        self, order_id: Optional[str] = None, order: Optional[Order] = None
    ):
        ...

    async def run(self) -> Optional[asyncio.Task]:
        ...

    async def close(self):
        ...
      
    def calculate_data_range(self,
          start_date: date,
          end_date: date, 
          ) -> List[Optional[pd.DatetimeIndex]]:
        
        scale_factor_hours = get_scale_factor(start_date, end_date)
        scale_factor_minutes = scale_factor_hours * 60

        data_points = scale_factor_hours if self.scale == TimeScale.day else scale_factor_minutes

        total_data_points = days * data_points
        periods =  ceil(total_data_points / get_max_data_points_per_load())
        total_periods = 2 if periods == 1 else periods

        return pd.date_range(start_date, end_date, periods=total_periods)

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            raise AssertionError("Must instantiate before usage")

        return cls.__instance  # type: ignore
