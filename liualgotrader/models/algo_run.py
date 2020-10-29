import json
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from asyncpg.pool import Pool

from liualgotrader.common import config


class AlgoRun:
    def __init__(self, strategy_name: str, batch_id: str):
        self.run_id: Any[None, int] = None
        self.strategy_name = strategy_name
        self.batch_id = batch_id

    async def save(
        self, pool: Pool = None, env: str = None, ref_algo_run_id: int = None
    ) -> None:
        if not pool:
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                if not ref_algo_run_id:
                    q = """
                        INSERT INTO algo_run (algo_name, algo_env, build_number, parameters, batch_id)
                        VALUES ($1, $2, $3, $4, $5)
                        RETURNING algo_run_id
                        """

                    self.run_id = await con.fetchval(
                        q,
                        self.strategy_name,
                        env if env else config.env,
                        config.build_label,
                        json.dumps(
                            {
                                "DSN": config.dsn,
                            }
                        ),
                        self.batch_id,
                    )
                else:
                    q = """
                        INSERT INTO algo_run (algo_name, algo_env, build_number, parameters, batch_id, ref_algo_run)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING algo_run_id
                        """
                    self.run_id = await con.fetchval(
                        q,
                        self.strategy_name,
                        env if env else config.env,
                        config.build_label,
                        json.dumps(
                            {
                                "DSN": config.dsn,
                            }
                        ),
                        self.batch_id,
                        ref_algo_run_id,
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
    ) -> List:
        rc: Dict = {}
        if not pool:
            pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT build_number, batch_id, algo_name, algo_env, date_trunc('minute', min(start_time)) as start
                        FROM algo_run
                        GROUP BY batch_id, algo_name, algo_env, build_number
                        ORDER BY start DESC
                        LIMIT $1
                    """,
                    nax_batches,
                )

                if rows:
                    return [list(map(str, row.values())) for row in rows]

        return []

    @classmethod
    async def get_batch_list_by_date(
        cls,
        batch_date: date,
        pool: Pool = None,
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
                        WHERE start_time >= $1 and start_time < $2
                    """,
                    batch_date,
                    batch_date + timedelta(days=1),
                )

                if rows:
                    for row in rows:
                        if row[0] not in rc:
                            rc[row[0]] = [list(row.values())[1:]]
                        else:
                            rc[row[0]].append(list(row.values())[1:])

        return rc

    @classmethod
    async def get_batch_details(
        cls, batch_id: str, pool: Pool = None
    ) -> List[Tuple[int, datetime, datetime, str]]:
        rc: List = []
        if not pool:
            pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT algo_run_id, start_time, end_time, parameters, algo_name
                        FROM algo_run
                        WHERE batch_id = $1
                        ORDER BY start_time DESC
                    """,
                    batch_id,
                )

                if rows:
                    rc = [
                        (
                            row[0],
                            row[1],
                            row[2],
                            row[3],
                        )
                        for row in rows
                    ]

        return rc
