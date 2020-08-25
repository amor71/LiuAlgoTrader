import json
from typing import Dict

from asyncpg.pool import Pool
from deprecated import deprecated


@deprecated(reason="should not be used")
class Trade:
    sell_price: float
    sell_indicators: Dict
    is_win: bool

    def __init__(
        self,
        algo_run_id: int,
        symbol: str,
        qty: int,
        price: float,
        indicators: dict,
    ):
        """
        create a trade object, which mean a "buy" operation, and creating a transaction_id,
        which may be used later to update the "sell"
        :param algo_run_id: id of the algorithm making the transaction
        :param symbol: stock symbol
        :param qty: amount being purchased
        :param price: buy price
        :param indicators: buy indicators
        """
        self.algo_run_id = algo_run_id
        self.symbol = symbol
        self.qty = qty
        self.buy_price = price
        self.buy_indicators = indicators
        self.trade_id = None

    async def save_buy(self, pool: Pool, client_buy_time: str):
        async with pool.acquire() as con:
            async with con.transaction():
                self.trade_id = await con.fetchval(
                    """
                        INSERT INTO trades (algo_run_id, symbol, qty, buy_price, buy_indicators, client_buy_time)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        RETURNING trade_id
                    """,
                    self.algo_run_id,
                    self.symbol,
                    self.qty,
                    self.buy_price,
                    json.dumps(self.buy_indicators),
                    client_buy_time,
                )

    async def save_sell(
        self, pool: Pool, price: float, indicators: dict, client_sell_time: str
    ):
        self.sell_price = price
        self.sell_indicators = indicators
        self.is_win = self.sell_price > self.buy_price
        async with pool.acquire() as con:
            async with con.transaction():
                await con.execute(
                    """
                        UPDATE trades SET client_sell_time=$5, sell_price=$1, sell_indicators=$2, is_win=$3, sell_time='now()'
                        WHERE trade_id = $4
                    """,
                    self.sell_price,
                    json.dumps(self.sell_indicators),
                    self.is_win,
                    self.trade_id,
                    client_sell_time,
                )
