from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


class KeyStore:
    @classmethod
    async def load(cls, key: str):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            val = await con.fetchval(
                """
                    SELECT 
                        value
                    FROM 
                        keystore
                    WHERE 
                        key = $1
                """,
                key,
            )

            return val

    @classmethod
    async def save(cls, key: str, value: str):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            await con.execute(
                """
                    INSERT INTO 
                        keystore(key, value)
                    VALUES 
                        ($1, $2)
                    ON CONFLICT(key) 
                        DO UPDATE 
                            SET value = $2;
                """,
                key,
                value,
            )
