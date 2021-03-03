from datetime import date

from pandas import DataFrame

from liualgotrader.common import config
from liualgotrader.common.database import fetch_as_dataframe
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
                                INSERT INTO gain_loss (symbol, algo_run_id, gain_percentage, gain_value)
                                VALUES ($1, $2, $3, $4)
                                RETURNING gain_loss_id
                            """,
                            row.symbol,
                            row.algo_run_id,
                            row.gain_percentage,
                            row.gain_value,
                        )
                except Exception as e:
                    tlog(f"[ERROR] inserting {row} resulted in exception {e}")

    @classmethod
    async def load(cls, start_date: date) -> DataFrame:
        q = """
            SELECT symbol, algo_name, algo_env, start_time, gain_percentage, gain_value
            FROM gain_loss as g, algo_run as a
            WHERE 
                g.algo_run_id = a.algo_run_id AND
                start_time >= $1
            ORDER BY symbol, algo_name, start_time
            """

        return await fetch_as_dataframe(q, start_date)


class TradeAnalysis:
    @classmethod
    async def save(cls, df: DataFrame):
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            for _, row in df.iterrows():
                try:
                    async with con.transaction():
                        _ = await con.fetchval(
                            """
                                INSERT INTO trade_analysis (symbol, algo_run_id, gain_percentage, gain_value, r_units, start_tstamp, end_tstamp)
                                VALUES ($1, $2, $3, $4, $5, $6, $7)
                                RETURNING trade_analysis_id
                            """,
                            row.symbol,
                            row.algo_run_id,
                            row.gain_percentage,
                            row.gain_value,
                            row.r_units,
                            row.start_time.to_pydatetime(),
                            row.end_time.to_pydatetime(),
                        )
                except Exception as e:
                    tlog(f"[ERROR] inserting {row} resulted in exception {e}")

    @classmethod
    async def load(cls, start_date: date) -> DataFrame:
        q = """
            SELECT symbol, algo_name, algo_env, r_units, gain_percentage, gain_value, t.start_tstamp, t.end_tstamp
            FROM trade_analysis as t, algo_run as a
            WHERE 
                t.algo_run_id = a.algo_run_id AND
                start_time >= $1
            ORDER BY symbol, algo_name, start_time
            """

        return await fetch_as_dataframe(q, start_date)
