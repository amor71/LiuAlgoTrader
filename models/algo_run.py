import json

from asyncpg.pool import Pool

from common import config, trading_data


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
                    trading_data.build_label,
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
