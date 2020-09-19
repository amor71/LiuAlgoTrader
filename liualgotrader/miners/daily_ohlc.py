import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from json.decoder import JSONDecodeError
from typing import Dict, List, Optional

import requests
from alpaca_trade_api.common import get_polygon_credentials
from alpaca_trade_api.polygon.entity import Ticker

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog
from liualgotrader.miners.base import Miner
from liualgotrader.models.ticker_data import TickerData


class DailyOHLC(Miner):
    def __init__(
        self,
        days: int,
        min_stock_price: Optional[float],
        max_stock_price: Optional[float],
    ):
        self._num_workers = 20
        self._days = days
        self._min_stock_price = min_stock_price
        self._max_stock_price = max_stock_price
        super().__init__(name="DailyOHLC")

    @property
    def days(self) -> int:
        return self._days

    @property
    def min_stock_price(self) -> Optional[float]:
        return self._min_stock_price

    @property
    def max_stock_price(self) -> Optional[float]:
        return self._max_stock_price

    async def run(self) -> bool:
        return False
