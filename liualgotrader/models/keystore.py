from liualgotrader.common import config


class KeyStore:
    @classmethod
    async def load(cls, key: str, algo_name: str, context: str):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            val = await con.fetchval(
                """
                    SELECT value
                    FROM keystore
                    WHERE 
                        key = $1 
                        AND context = $3
                        AND algo_name = $2;
                """,
                key,
                algo_name,
                context,
            )

            return val

    @classmethod
    async def save(cls, key: str, value: str, algo_name: str, context: str):
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                val = await con.fetchval(
                    """
                        INSERT INTO  keystore(algo_name, key, value, context)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT(algo_name, key, context) 
                            DO UPDATE 
                                SET value = $3;
                    """,
                    algo_name,
                    key,
                    value,
                    context,
                )

                return val
