import asyncio
import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd

from liualgotrader.common.types import QueueMapper
from liualgotrader.models.algo_run import AlgoRun


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

    async def is_shortable(self, symbol) -> bool:
        ...

    async def is_order_completed(self, order) -> Tuple[bool, float]:
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
    ):
        ...

    async def get_order(self, order_id: str):
        ...

    async def cancel_order(self, order_id: str):
        ...

    async def run(self) -> Optional[asyncio.Task]:
        ...

    async def close(self):
        ...

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            raise AssertionError("Must instantiate before usage")

        return cls.__instance  # type: ignore
