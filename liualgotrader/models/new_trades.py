"""Save trade details to repository"""
import json
from datetime import datetime
from typing import Dict, List, Tuple

from asyncpg.pool import Pool

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


class NewTrade:
    def __init__(
        self,
        algo_run_id: int,
        symbol: str,
        operation: str,
        qty: float,
        price: float,
        indicators: dict,
    ):
        """
        create a new_trade object
        :param algo_run_id: id of the algorithm making the transaction
        :param symbol: stock symbol
        :param operation: buy or sell
        :param qty: amount being purchased
        :param price: buy price
        :param indicators: buy indicators
        """
        self.algo_run_id = algo_run_id
        self.symbol = symbol
        self.qty = qty
        self.price = price
        self.indicators = indicators
        self.operation = operation
        self.trade_id = None

    async def save(
        self,
        pool: Pool,
        client_buy_time: str,
        stop_price=None,
        target_price=None,
        trade_fee=0.0,
    ):
        async with pool.acquire() as con:
            async with con.transaction():
                try:
                    indicators_s = json.dumps(
                        self.indicators or {}, allow_nan=False
                    )
                except ValueError:
                    indicators_s = json.dumps({})

                self.trade_id = await con.fetchval(
                    """
                        INSERT INTO new_trades (algo_run_id, symbol, operation, qty, price, indicators, client_time, stop_price, target_price, trade_fee)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                        RETURNING trade_id
                    """,
                    self.algo_run_id,
                    self.symbol,
                    self.operation,
                    self.qty,
                    self.price,
                    indicators_s,
                    client_buy_time,
                    stop_price,
                    target_price,
                    trade_fee,
                )

    @classmethod
    async def expire_trade(cls, pool: Pool, trade_id: int) -> None:
        async with pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """
                        UPDATE new_trades SET expire_tstamp='now()' WHERE trade_id=$1
                    """,
                    trade_id,
                )

    @classmethod
    async def load_latest(
        cls, pool: Pool, symbol: str, strategy_name: str
    ) -> Tuple[int, float, float, float, Dict, datetime]:
        async with pool.acquire() as con:
            async with con.transaction():
                row = await con.fetchrow(
                    """
                        SELECT t.algo_run_id, t.price, t.stop_price, t.target_price, t.indicators, t.tstamp 
                        FROM new_trades as t, algo_run as a
                        WHERE 
                            t.algo_run_id=a.algo_run_id AND
                            a.algo_name=$2 AND
                            symbol=$1 
                        ORDER BY tstamp DESC LIMIT 1
                    """,
                    symbol,
                    strategy_name,
                )

                if row:
                    return (
                        int(row[0]),
                        float(row[1]),
                        float(row[2] or 0.0),
                        float(row[3] or 0.0),
                        json.loads(row[4] or "{}"),
                        row[5],
                    )
                tlog(f"{symbol} no data for strategy {strategy_name}")
                raise ValueError

    @classmethod
    async def get_run_symbols(
        cls, run_id: int, pool: Pool = None
    ) -> List[str]:
        rc: List = []
        if not pool:
            pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                rows = await con.fetch(
                    """
                        SELECT DISTINCT symbol
                        FROM new_trades
                        WHERE algo_run_id = $1 and expire_tstamp is null
                    """,
                    run_id,
                )

                if rows:
                    rc = [row[0] for row in rows]

        return rc

    @classmethod
    async def rename_algo_run_id(
        cls, new_run_id: int, old_run_id: int, symbol: str, pool: Pool = None
    ) -> None:
        if not pool:
            pool = config.db_conn_pool

        async with pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """
                        UPDATE 
                            new_trades 
                        SET 
                            algo_run_id=$1 
                        WHERE 
                            algo_run_id=$2 AND
                            symbol=$3
                    """,
                    new_run_id,
                    old_run_id,
                    symbol,
                )

    @classmethod
    async def get_latest_algo_run_id(
        cls, symbol: str, pool: Pool = None
    ) -> int:
        if not pool:
            pool = config.db_conn_pool
        async with pool.acquire() as con:
            async with con.transaction():
                val = await con.fetchval(
                    """
                        SELECT  algo_run_id
                        FROM new_trades
                        WHERE symbol = $1
                        ORDER BY tstamp DESC
                        LIMIT 1
                    """,
                    symbol,
                )

                return val
