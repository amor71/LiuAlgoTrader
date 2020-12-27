from typing import Dict

import asyncpg
import pandas as pd

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


async def create_db_connection(dsn: str = None) -> bool:
    if config.db_conn_pool:
        return False

    config.db_conn_pool = await asyncpg.create_pool(
        dsn=dsn if dsn else config.dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    tlog("db connection pool initialized")
    return True


async def fetch_as_dataframe(query: str, *args) -> pd.DataFrame:
    await create_db_connection()
    if config.db_conn_pool:
        async with config.db_conn_pool.acquire() as con:
            stmt = await con.prepare(query)
            columns = [a.name for a in stmt.get_attributes()]
            data = await stmt.fetch(*args)
            return pd.DataFrame(data=data, columns=columns)
    else:
        raise Exception("Failed to connect to database")
