import asyncio
import json
from datetime import date, datetime
from typing import Dict

import asyncpg
from pandas import DataFrame

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog


class Portfolio:
    def __init__(
        self,
        portfolio_id: str,
        portfolio_size: int,
        stock_count: int,
        parameters: Dict,
    ):
        self.portfolio_id = portfolio_id
        self.portfolio_size = portfolio_size
        self.stock_count = stock_count
        self.parameters = parameters

    @classmethod
    async def load_by_batch_id(cls, batch_id: str):
        try:
            pool = config.db_conn_pool
        except AttributeError:
            await create_db_connection()
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            data = await con.fetchrow(
                """
                    SELECT p.portfolio_id, p.size, p.stock_count, p.parameters
                    FROM 
                        portfolio as p, portfolio_batch_ids as b
                    WHERE
                        p.portfolio_id = b.portfolio_id
                        AND b.batch_id = $1
                """,
                batch_id,
            )

            if data:
                return Portfolio(*data)

    @classmethod
    async def load_by_portfolio_id(cls, portfolio_id: str):
        try:
            pool = config.db_conn_pool
        except AttributeError:
            await create_db_connection()
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            data = await con.fetchrow(
                """
                    SELECT p.portfolio_id, p.size, p.stock_count, p.parameters
                    FROM 
                        portfolio as p
                    WHERE
                        p.portfolio_id = $1
                """,
                portfolio_id,
            )

            if data:
                return Portfolio(*data)

    @classmethod
    async def save(
        cls,
        portfolio_id: str,
        portfolio_size: int,
        stock_count: int,
        parameters: Dict,
    ):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            await con.execute(
                """
                    INSERT INTO portfolio (portfolio_id, size, stock_count, parameters)
                    VALUES ($1, $2, $3, $4)
                """,
                portfolio_id,
                portfolio_size,
                stock_count,
                json.dumps(parameters),
            )

    @classmethod
    async def associate_batch_id_to_profile(
        cls, portfolio_id: str, batch_id: str
    ) -> None:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            await con.execute(
                """
                    INSERT INTO portfolio_batch_ids (portfolio_id, batch_id)
                    VALUES ($1, $2)
                """,
                portfolio_id,
                batch_id,
            )

    @classmethod
    async def exists(cls, portfolio_id: str) -> bool:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            result = await con.fetchval(
                """
                    SELECT EXISTS (
                        SELECT 1 
                        FROM portfolio
                        WHERE portfolio_id = $1
                    )
                """,
                portfolio_id,
            )
            return result
