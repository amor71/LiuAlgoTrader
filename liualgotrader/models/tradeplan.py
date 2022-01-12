import json
from datetime import datetime
from typing import List, Optional

import asyncpg

from liualgotrader.common import config


class TradePlan:
    def __init__(
        self,
        strategy_name: str,
        parameters: dict,
        portfolio_id: str,
    ):
        self.strategy_name = strategy_name
        self.parameters = parameters
        self.portfolio_id = portfolio_id

    def __str__(self):
        return f"{self.strategy_name}:{self.parameters}"

    @classmethod
    async def load(cls) -> List["TradePlan"]:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT
                            strategy_name, portfolio_id, parameters
                        FROM 
                            trade_plan
                        WHERE 
                            expire_tstamp is null
                            AND start_date <= NOW()
                    """,
                )

                return [
                    TradePlan(
                        strategy_name=r["strategy_name"],
                        portfolio_id=r["portfolio_id"],
                        parameters=json.loads(r["parameters"]),
                    )
                    for r in rows
                ]

    @classmethod
    async def get_new_entries(
        cls, since: datetime
    ) -> Optional[List["TradePlan"]]:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            q = f"""
                    SELECT
                        strategy_name, portfolio_id, parameters
                    FROM 
                        trade_plan
                    WHERE 
                        expire_tstamp is null
                        AND start_date <= NOW()
                        AND create_tstamp > '{since}'
                """
            rows = await con.fetch(q)

            return [
                TradePlan(
                    strategy_name=r["strategy_name"],
                    portfolio_id=r["portfolio_id"],
                    parameters=json.loads(r["parameters"]),
                )
                for r in rows
            ]
