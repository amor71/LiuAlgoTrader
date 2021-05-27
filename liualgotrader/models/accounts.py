import datetime
import json
from typing import Dict

import pandas as pd

from liualgotrader.common import config
from liualgotrader.common.database import fetch_as_dataframe
from liualgotrader.common.tlog import tlog


class Accounts:
    @classmethod
    async def create(
        cls,
        balance: float,
        allow_negative: bool = False,
        credit_line: float = 0.0,
        details: Dict = {},
    ) -> int:
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                return await con.fetchval(
                    """
                        INSERT INTO 
                            accounts (balance, allow_negative, credit_line, details)
                        VALUES
                            ($1, $2, $3, $4)
                        RETURNING account_id;
                    """,
                    balance,
                    allow_negative,
                    credit_line,
                    json.dumps(details),
                )

    @classmethod
    async def get_balance(cls, account_id: int) -> float:
        pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                return await con.fetchval(
                    """
                        SELECT
                            balance
                        FROM 
                            accounts 
                        WHERE
                            account_id = $1
                    """,
                    account_id,
                )

    @classmethod
    async def add_transaction(
        cls,
        account_id: int,
        amount: float,
        tstamp: datetime.datetime = None,
        details: Dict = {},
    ):
        pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                if tstamp:
                    await con.execute(
                        """
                            INSERT INTO 
                                account_transactions (account_id, amount, tstamp, details)
                            VALUES
                                ($1, $2, $3, $4);
                        """,
                        account_id,
                        amount,
                        tstamp,
                        json.dumps(details),
                    )
                else:
                    await con.execute(
                        """
                            INSERT INTO 
                                account_transactions (account_id, amount, details)
                            VALUES
                                ($1, $2, $3);
                        """,
                        account_id,
                        amount,
                        json.dumps(details),
                    )

    @classmethod
    async def get_transactions(cls, account_id: int) -> pd.DataFrame:
        q = """
            SELECT
                tstamp, amount
            FROM 
                account_transactions 
            WHERE
                account_id = $1
            """

        df = await fetch_as_dataframe(q, account_id)
        return df.set_index("tstamp", drop=True)
