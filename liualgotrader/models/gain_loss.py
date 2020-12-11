from pandas import DataFrame

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


class GainLoss:
    @classmethod
    async def save(cls, df: DataFrame):
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            for _, row in df.iterrows():
                try:
                    async with con.transaction():
                        _ = await con.fetchval(
                            """
                                INSERT INTO gain_loss (symbol, algo_run_id, gain_precentage, gain_value)
                                VALUES ($1, $2, $3, $4)
                                RETURNING gain_loss_id
                            """,
                            row.symbol,
                            row.algo_run_id,
                            row.gain_precentage,
                            row.gain_value,
                        )
                except Exception as e:
                    tlog(f"[ERROR] inserting {row} resulted in exception {e}")
