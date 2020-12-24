from datetime import date

from pandas import DataFrame

from liualgotrader.common import config
from liualgotrader.common.database import fetch_as_dataframe
from liualgotrader.common.tlog import tlog


class Portfolio:
    @classmethod
    async def save(cls, df: DataFrame, id: str):
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            for _, row in df.iterrows():
                try:
                    async with con.transaction():
                        _ = await con.fetchval(
                            """
                                INSERT INTO portfolio(id, symbol, rank, qty)
                                VALUES ($1, $2, $3, #4)
                                RETURNING portfolio_id
                            """,
                            id,
                            row.symbol,
                            row.ranked_slope,
                            row.qty,
                        )
                except Exception as e:
                    tlog(f"[ERROR] inserting {row} resulted in exception {e}")
