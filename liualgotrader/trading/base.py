import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from liualgotrader.common.exceptions import MarketClosedToday
from liualgotrader.common.types import QueueMapper


class Trader:
    __instance: object = None

    def __init__(self, queues: QueueMapper):
        self.queues = queues
        Trader.__instance = self

    def __repr__(self):
        return type(self).__name__

    def get_market_schedule(self) -> Tuple[datetime, datetime]:
        """Get market open, close in NYC timezone, timedelta to close.

        Returns
        -------
        datetime
            market's open datetime in NYC timezone
        datetime
            market's close datetime in NYC timezone
        """
        pass

    def is_market_open_today(self) -> bool:
        pass

    def get_time_market_close(self) -> timedelta:
        pass

    def get_position(self, symbol: str) -> float:
        pass

    async def reconnect(self):
        pass

    async def get_tradeable_symbols(self) -> List[str]:
        pass

    async def get_shortable_symbols(self) -> List[str]:
        pass

    async def is_shortable(self, symbol) -> bool:
        pass

    async def submit_order(
        self,
        symbol: str,
        qty: int,
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
        pass

    async def cancel_order(self, order_id: str):
        pass

    async def run(self) -> Optional[asyncio.Task]:
        pass

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            raise AssertionError("Must instantiate before usage")

        return cls.__instance  # type: ignore
