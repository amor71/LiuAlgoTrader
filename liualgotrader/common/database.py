import asyncpg
import pandas as pd

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


async def create_db_connection(dsn: str = None) -> None:
    # if not hasattr(config, "db_conn_pool"):
    _dsn = dsn or config.dsn
    config.db_conn_pool = await asyncpg.create_pool(
        dsn=_dsn,
        min_size=2,
        max_size=10,
    )

    tlog(f"db connection pool initialized w {_dsn}")


async def fetch_as_dataframe(query: str, *args) -> pd.DataFrame:
    try:
        config.db_conn_pool
    except (NameError, AttributeError):
        await create_db_connection()

    async with config.db_conn_pool.acquire() as con:
        stmt = await con.prepare(query)
        columns = [a.name for a in stmt.get_attributes()]
        data = await stmt.fetch(*args)

        return (
            pd.DataFrame(data=data, columns=columns)
            if data and len(data) > 0
            else pd.DataFrame()
        )
