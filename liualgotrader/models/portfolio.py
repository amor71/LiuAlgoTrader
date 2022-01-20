import json
from typing import Dict, List, Optional, Tuple

import tabulate
from pandas import DataFrame

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import AssetType
from liualgotrader.models.accounts import Accounts


class Portfolio:
    def __init__(
        self,
        portfolio_id: str,
        portfolio_size: float,
        asset_type: AssetType,
        account_id: Optional[int],
        parameters: Dict,
    ):
        self.portfolio_id = portfolio_id
        self.portfolio_size = portfolio_size
        self.parameters = parameters
        self.account_id = account_id
        self.asset_type = AssetType[str(asset_type)]

    def __str__(self):
        return f"id={self.portfolio_id} account-id={self.account_id} size={self.portfolio_size} asset_type={self.asset_type}, params={self.parameters}"

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
                    SELECT p.portfolio_id, p.size, p.assets, p.account_id, p.parameters
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
                    SELECT p.portfolio_id, p.size, p.assets, p.account_id, p.parameters
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
        asset_type: AssetType = AssetType.US_EQUITIES,
        external_account_id: Optional[str] = None,
        broker: Optional[str] = None,
    ):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                account_id = await Accounts.create(
                    portfolio_size,
                    allow_negative=credit > 0.0,
                    credit_line=credit,
                    details=parameters,
                )
                await con.execute(
                    """
                        INSERT INTO portfolio (portfolio_id, size, account_id, assets, parameters, external_account_id, broker)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    portfolio_id,
                    portfolio_size,
                    account_id,
                    asset_type.name,
                    json.dumps(parameters),
                    external_account_id,
                    broker,
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
    async def is_associated(cls, portfolio_id: str, batch_id: str) -> bool:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            result = await con.fetchval(
                """
                    SELECT EXISTS (
                        SELECT 1 
                        FROM portfolio_batch_ids
                        WHERE portfolio_id = $1 AND batch_id=$2
                    )
                """,
                portfolio_id,
                batch_id,
            )
            return result

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
    async def get_portfolio_account_balance(cls, portfolio_id: str) -> float:
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            return await con.fetchval(
                """
                    SELECT
                        balance
                    FROM 
                        accounts as a, portfolio as f 
                    WHERE
                        a.account_id = f.account_id
                        AND portfolio_id = $1
                """,
                portfolio_id,
            )

    @classmethod
    async def get_external_account_id(
        cls, portfolio_id: str
    ) -> Tuple[Optional[str], Optional[str]]:
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            r = await con.fetchrow(
                """
                    SELECT
                        external_account_id, broker
                    FROM 
                        portfolio
                    WHERE
                        portfolio_id = $1
                """,
                portfolio_id,
            )

            return (r["external_account_id"], r["broker"])

    @classmethod
    async def list_portfolios(cls) -> List[str]:
        try:
            pool = config.db_conn_pool
        except AttributeError:
            await create_db_connection()
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT
                            portfolio_id , a.tstamp as last_transaction, size, parameters ,assets, p.tstamp 
                        FROM
                            portfolio as p
                        LEFT JOIN account_transactions as a
                        ON
                            p.account_id = a.account_id
                        WHERE
                            p.expire_tstamp is NULL
                        ORDER BY 
                            p.tstamp DESC
                    """,
                )
                return DataFrame(
                    data=rows,
                    columns=[
                        "portfolio_id",
                        "last_transaction",
                        "size",
                        "parameters",
                        "assets",
                        "tstamp",
                    ],
                )
