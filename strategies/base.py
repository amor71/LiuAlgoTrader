from datetime import datetime

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

import trading_data
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
