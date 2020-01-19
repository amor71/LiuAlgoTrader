import json


class AlgoRun:
    def __init__(
        self, name: str, environment: str, build: str, parameters: dict
    ):
        self.name = name
        self.environment = environment
        self.build = build
        self.parameters = parameters

    async def save(self, db_connection):
        async with db_connection.transaction():
            await db_connection.execute(
                """
                    INSERT INTO algo_run (algo_name, algo_env, build_number, parameters)
                    VALUES ($1, $2, $3, $4)
                """,
                self.name,
                self.environment,
                self.build,
                json.dumps(self.parameters),
            )
