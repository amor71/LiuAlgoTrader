"""Base Class for Strategies"""
from datetime import datetime

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from common import config, trading_data
from models.algo_run import AlgoRun


class Strategy:
    def __init__(self, name: str, trading_api: tradeapi, data_api: tradeapi):
        self.name = name
        self.trading_api = trading_api
        self.data_api = data_api
        self.algo_run = AlgoRun(strategy_name=self.name)

    async def create(self):
        await self.algo_run.save(pool=trading_data.db_conn_pool)

    async def run(
        self, symbol: str, position: int, minute_history: df, now: datetime
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
