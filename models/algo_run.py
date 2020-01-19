import json

from asyncpg.pool import Pool


class AlgoRun:
    def __init__(
        self, name: str, environment: str, build: str, parameters: dict
    ):
        """
        :param name: algorithm name
        :param environment: which environment (paper or production)
        :param build: GIT build number
        :param parameters: algorithm parameters (usually OS environment vars)
        """

        self.name = name
        self.environment = environment
        self.build = build
        self.parameters = parameters
        self.algo_run_id = None

    async def save(self, pool: Pool):
        async with pool.acquire() as con:
            async with con.transaction():
                self.algo_run_id = await con.fetchval(
                    """
                        INSERT INTO algo_run (algo_name, algo_env, build_number, parameters)
                        VALUES ($1, $2, $3, $4)
                        RETURNING algo_run_id
                    """,
                    self.name,
                    self.environment,
                    self.build,
                    json.dumps(self.parameters),
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
                    self.algo_run_id,
                )
