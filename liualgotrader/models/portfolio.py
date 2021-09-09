import json
from typing import Dict, Tuple

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.models.accounts import Accounts


class Portfolio:
    def __init__(
        self,
        portfolio_id: str,
        portfolio_size: float,
        parameters: Dict,
    ):
        self.portfolio_id = portfolio_id
        self.portfolio_size = portfolio_size
        self.parameters = parameters

    @classmethod
    async def load_by_batch_id(cls, batch_id: str):
        try:
            pool = config.db_conn_pool
        except AttributeError:
            await create_db_connection()
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            data = await con.fetchrow(
                """
                    SELECT p.portfolio_id, p.size, p.parameters
                    FROM 
                        portfolio as p, portfolio_batch_ids as b
                    WHERE
                        p.portfolio_id = b.portfolio_id
                        AND b.batch_id = $1
                """,
                batch_id,
            )

            if data:
                return Portfolio(*data)

    @classmethod
    async def load_by_portfolio_id(cls, portfolio_id: str):
        try:
            pool = config.db_conn_pool
        except AttributeError:
            await create_db_connection()
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            data = await con.fetchrow(
                """
                    SELECT p.portfolio_id, p.size, p.parameters
                    FROM 
                        portfolio as p
                    WHERE
                        p.portfolio_id = $1
                """,
                portfolio_id,
            )

            if data:
                return Portfolio(*data)

    @classmethod
    async def save(
        cls,
        portfolio_id: str,
        portfolio_size: float,
        credit: float,
        parameters: Dict,
    ):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                account_id = await Accounts.create(
                    portfolio_size,
                    allow_negative=credit > 0.0,
                    credit_line=credit,
                    db_connection=con,
                    details=parameters,
                )
                await con.execute(
                    """
                        INSERT INTO portfolio (portfolio_id, size, account_id, parameters)
                        VALUES ($1, $2, $3, $4)
                    """,
                    portfolio_id,
                    portfolio_size,
                    account_id,
                    json.dumps(parameters),
                )

    @classmethod
    async def associate_batch_id_to_profile(
        cls, portfolio_id: str, batch_id: str
    ) -> None:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            await con.execute(
                """
                    INSERT INTO portfolio_batch_ids (portfolio_id, batch_id)
                    VALUES ($1, $2)
                """,
                portfolio_id,
                batch_id,
            )

    @classmethod
    async def exists(cls, portfolio_id: str) -> bool:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            result = await con.fetchval(
                """
                    SELECT EXISTS (
                        SELECT 1 
                        FROM portfolio
                        WHERE portfolio_id = $1
                    )
                """,
                portfolio_id,
            )
            return result

    @classmethod
    async def load_details(cls, portfolio_id: str) -> Tuple[int, float]:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            result = await con.fetchrow(
                """
                    SELECT account_id, size
                    FROM portfolio
                    WHERE portfolio_id = $1;
                """,
                portfolio_id,
            )
            return result[0], result[1]
