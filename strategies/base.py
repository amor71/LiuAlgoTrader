"""Base Class for Strategies"""
from datetime import datetime

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from common import config
from models.algo_run import AlgoRun


class Strategy:
    def __init__(self, name: str, batch_id: str):
        self.name = name
        self.algo_run = AlgoRun(strategy_name=self.name, batch_id=batch_id)

    async def create(self):
        await self.algo_run.save(pool=config.db_conn_pool)

    async def run(
        self,
        symbol: str,
        position: int,
        minute_history: df,
        now: datetime,
        portfolio_value: float = None,
        trading_api: tradeapi = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> bool:
        return False

    async def is_sell_time(self, now: datetime):
        return (
            True
            if (
                (now - config.market_open).seconds // 60
                >= config.market_cool_down_minutes
                or config.bypass_market_schedule
            )
            and (config.market_close - now).seconds // 60 > 15
            else False
        )

    async def is_buy_time(self, now: datetime):
        return (
            True
            if config.trade_buy_window
            > (now - config.market_open).seconds // 60
            > config.market_cool_down_minutes
            or config.bypass_market_schedule
            else False
        )

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        pass

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        pass
