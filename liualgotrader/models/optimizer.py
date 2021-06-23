from typing import List

import asyncpg

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection


class OptimizerRun:
    @classmethod
    async def save(
        cls,
        optimizer_session_id: str,
        batch_id: str,
    ):
        async with config.db_conn_pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """
                        INSERT INTO optimizer_run (optimizer_session_id, batch_id)
                        VALUES ($1, $2)
                    """,
                    optimizer_session_id,
                    batch_id,
                )

    @classmethod
    async def get_portfolio_ids(
        cls,
        optimizer_session_id: str,
    ) -> List[str]:
        try:
            pool = config.db_conn_pool
        except AttributeError:
            await create_db_connection()
            pool = config.db_conn_pool

        async with config.db_conn_pool.acquire() as con:
            recrods = await con.fetch(
                """
                    SELECT 
                        p.portfolio_id
                    FROM 
                        optimizer_run as o, portfolio_batch_ids as p
                    WHERE
                        o.batch_id = p.batch_id
                        AND optimizer_session_id = $1;
                """,
                optimizer_session_id,
            )

        return [row[0] for row in recrods]
