from typing import List, Tuple
from datetime import datetime
from asyncpg.pool import Pool

from liualgotrader.common import config


class TrendingTickers:
    def __init__(self, batch_id: str):
        self.batch_id = batch_id
        self.trending_id: int = 0

    async def save(self, symbols: List[str], pool: Pool = None) -> int:
        if not pool:
            pool = config.db_conn_pool

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
    async def load(cls, batch_id, pool: Pool = None) -> List[Tuple[str, datetime]]:
        if not pool:
            pool = config.db_conn_pool

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
