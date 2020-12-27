from datetime import date, datetime
from typing import List, Tuple

from asyncpg.pool import Pool
from pandas import DataFrame

from liualgotrader.common import config
from liualgotrader.common.database import fetch_as_dataframe


class TrendingTickers:
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.trending_id: int = 0

    async def save(self, symbols: List[str], pool: Pool = None) -> int:
        if not pool:
            pool = config.db_conn_pool
        if not pool:
            raise Exception("invalid connection pool")
        async with pool.acquire() as con:
            async with con.transaction():
                for symbol in symbols:
                    self.trending_id = await con.fetchval(
                        """
                            INSERT INTO trending_tickers (batch_id, symbol)
                            VALUES ($1, $2)
                            RETURNING trending_id
                        """,
                        self.batch_id,
                        symbol,
                    )

        return self.trending_id

    @classmethod
    async def load(
        cls, batch_id, pool: Pool = None
    ) -> List[Tuple[str, datetime]]:
        if not pool:
            pool = config.db_conn_pool
        if not pool:
            raise Exception("invalid connection pool")
        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT symbol, create_tstamp
                        FROM trending_tickers 
                        WHERE batch_id=$1
                    """,
                    batch_id,
                )

                if rows:
                    return [(row[0], row[1]) for row in rows]
                else:
                    raise Exception("no data")

    @classmethod
    async def load_by_date_and_env(
        cls, env: str, start_date: date
    ) -> DataFrame:
        q = """
            SELECT 
                DISTINCT t.symbol, t.batch_id, t.create_tstamp
            FROM 
                trending_tickers as t
            JOIN 
                algo_run as a ON t.batch_id = a.batch_id
            WHERE
                algo_env = $1 AND
                start_time >= $2
            ORDER BY t.symbol, t.batch_id, t.create_tstamp
            """

        return await fetch_as_dataframe(q, env, start_date)
