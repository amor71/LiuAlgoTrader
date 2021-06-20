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
                        INSERT INTO optimizer_run (optimizer_session_id, batch_id,)
                        VALUES ($1, $2)
                    """,
                    optimizer_session_id,
                    batch_id,
                )
