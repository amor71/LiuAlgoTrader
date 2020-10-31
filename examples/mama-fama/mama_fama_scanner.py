"""follow the mama/fama indicator"""
from datetime import timedelta, datetime
from typing import List, Optional

import alpaca_trade_api as tradeapi

from liualgotrader.common import config
from liualgotrader.scanners.base import Scanner


class MamaFama(Scanner):
    name = "MamaFama"

    def __init__(
        self,
        data_api: tradeapi,
        recurrence: Optional[timedelta] = None,
        target_strategy_name: str = None,
    ):
        super().__init__(
            name=self.name,
            recurrence=recurrence,
            target_strategy_name=target_strategy_name,
            data_api=data_api,
        )

    async def run(self, back_time: datetime = None) -> List[str]:
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT symbol
                        FROM stock_ohlc 
                        WHERE (symbol, symbol_date) in 
                            (SELECT symbol, MAX(symbol_date) 
                             FROM stock_ohlc 
                             group by symbol) 
                             and indicators->'mama' > indicators->'fama';
                    """
                )
                return [row[0] for row in rows]
