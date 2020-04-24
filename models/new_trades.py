"""Save trade details to repository"""
import json

from asyncpg.pool import Pool


class NewTrade:
    def __init__(
        self,
        algo_run_id: int,
        symbol: str,
        operation: str,
        qty: int,
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
    ):
        async with pool.acquire() as con:
            async with con.transaction():
                self.trade_id = await con.fetchval(
                    """
                        INSERT INTO new_trades (algo_run_id, symbol, operation, qty, price, indicators, client_time, stop_price, target_price)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        RETURNING trade_id
                    """,
                    self.algo_run_id,
                    self.symbol,
                    self.operation,
                    self.qty,
                    self.price,
                    json.dumps(self.indicators),
                    client_buy_time,
                    stop_price,
                    target_price,
                )
