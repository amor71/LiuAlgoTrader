from dataclasses import dataclass
from typing import List

from asyncpg.exceptions import TooManyConnectionsError
from asyncpg.pool import Pool

from liualgotrader.common.tlog import tlog


@dataclass
class TickerData:
    name: str
    symbol: str
    description: str
    tags: List[str]
    similar_tickers: List[str]
    industry: str
    sector: str
    exchange: str

    async def save(self, pool: Pool) -> bool:
        try:
            async with pool.acquire() as con:
                async with con.transaction():
                    await con.execute(
                        """
                            INSERT INTO ticker_data (symbol, name, description, tags,
                                                     similar_tickers, industry, sector, exchange)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (symbol)
                            DO UPDATE
                                SET name=$2, description=$3, tags=$4, similar_tickers=$5, industry=$6,
                                    sector=$7, exchange=$8, modify_tstamp='now()'
                        """,
                        self.symbol,
                        self.name,
                        self.description,
                        self.tags,
                        self.similar_tickers,
                        self.industry,
                        self.sector,
                        self.exchange,
                    )
            return True
        except TooManyConnectionsError as e:
            tlog(
                f"too many db connections: {e}. Failed to write ticker {self.symbol}, will re-try"
            )

        return False
