import json
from typing import Dict, List

from asyncpg.pool import Pool

from common import config


class AlgoRun:
    def __init__(self, strategy_name: str, batch_id: str):
        self.run_id = None
        self.strategy_name = strategy_name
        self.batch_id = batch_id

    async def save(self, pool: Pool):
        async with pool.acquire() as con:
            async with con.transaction():
                self.run_id = await con.fetchval(
                    """
                        INSERT INTO algo_run (algo_name, algo_env, build_number, parameters, batch_id)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING algo_run_id
                    """,
                    self.strategy_name,
                    config.env,
                    config.build_label,
                    json.dumps(
                        {
                            "TRADE_BUY_WINDOW": config.trade_buy_window,
                            "DSN": config.dsn,
                        }
                    ),
                    self.batch_id,
                )

    async def update_end_time(self, pool: Pool, end_reason: str):
        async with pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """
                        UPDATE algo_run SET end_time='now()',end_reason=$1
                        WHERE algo_run_id = $2
                    """,
                    end_reason,
                    self.run_id,
                )

    @classmethod
    async def get_batches(
        cls, pool: Pool = None, nax_batches: int = 30
    ) -> Dict[str, List[str]]:
        rc: Dict = {}
        if not pool:
            pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT batch_id, algo_run_id, algo_name, algo_env, build_number, start_time
                        FROM algo_run
                        ORDER BY start_time DESC
                        LIMIT $1
                    """,
                    nax_batches,
                )

                if rows:
                    for row in rows:
                        if row[0] not in rc:
                            rc[row[0]] = [list(row.values())[1:]]
                        else:
                            rc[row[0]].append(list(row.values())[1:])

        return rc
