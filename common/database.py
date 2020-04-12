import asyncpg

from common import config, trading_data
from common.tlog import tlog


async def create_db_connection(dsn: str = None) -> None:
    trading_data.db_conn_pool = await asyncpg.create_pool(
        dsn=dsn if dsn else config.dsn, min_size=20, max_size=50
    )
    tlog("db connection pool initialized")
