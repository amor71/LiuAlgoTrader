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
                                INSERT INTO portfolio(portfolio_id, symbol, score, qty, volatility)
                                VALUES ($1, $2, $3, $4, $5)
                                RETURNING portfolio_entry_id
                            """,
                            id,
                            row.symbol,
                            row.score,
                            int(row.qty),
                            row.volatility,
                        )
                except Exception as e:
                    tlog(f"[ERROR] inserting {row} resulted in exception {e}")

    @classmethod
    async def load(cls, portfolio_id: str) -> DataFrame:
        q = """
            SELECT 
                symbol, qty, score, volatility
            FROM 
                portfolio
            WHERE 
                portfolio_id = $1 
            ORDER BY rank desc
            """

        return await fetch_as_dataframe(q, portfolio_id)
