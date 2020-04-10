from typing import List

from asyncpg.pool import Pool


class TickerData:
    def __init__(
        self,
        name: str,
        symbol: str,
        description: str,
        tags: List[str],
        similar_tickers: List[str],
        industry: str,
        sector: str,
        exchange: str,
    ):
        self.name = name
        self.symbol = symbol
        self.description = description
        self.tags = tags
        self.similar_tickers = similar_tickers
        self.industry = industry
        self.sector = sector
        self.exchange = exchange

    async def save(self, pool: Pool):
        pass
