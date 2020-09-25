"""Base Class for Strategies"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.models.algo_run import AlgoRun


class StrategyType(Enum):
    DAY_TRADE = 1
    SWING = 2


class Strategy:
    def __init__(
        self,
        name: str,
        type: StrategyType,
        batch_id: str,
        schedule: List[Dict],
        ref_run_id: int = None,
    ):
        self.name = name
        self.type = type
        self.ref_run_id = ref_run_id
        self.algo_run = AlgoRun(strategy_name=self.name, batch_id=batch_id)
        self.schedule = schedule

    async def create(self):
        await self.algo_run.save(
            pool=config.db_conn_pool, ref_algo_run_id=self.ref_run_id
        )

    async def run(
        self,
        symbol: str,
        shortable: bool,
        position: int,
        minute_history: df,
        now: datetime,
        portfolio_value: float = None,
        trading_api: tradeapi = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        return False, {}

    async def is_sell_time(self, now: datetime):
        return (
            True
            if (
                any(
                    (now - config.market_open).seconds // 60 >= schedule["start"]
                    for schedule in self.schedule
                )
                or (
                    hasattr(config, "bypass_market_schedule")
                    and config.bypass_market_schedule
                )
            )
            and (config.market_close - now).seconds // 60 > 15
            else False
        )

    async def is_buy_time(self, now: datetime):
        return (
            True
            if any(
                schedule["duration"]
                > (now - config.market_open).seconds // 60
                > schedule["start"]
                for schedule in self.schedule
            )
            or (
                hasattr(config, "bypass_market_schedule")
                and config.bypass_market_schedule
            )
            else False
        )

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        pass

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        pass
