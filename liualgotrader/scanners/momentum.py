import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import List, Optional

import requests
from alpaca_trade_api.rest import REST as tradeapi
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import DataConnectorType
from liualgotrader.models.ticker_data import StockOhlc
from liualgotrader.trading.base import Trader

from .base import Scanner


class Momentum(Scanner):
    name = "momentum"

    def __init__(
        self,
        recurrence: Optional[timedelta],
        target_strategy_name: Optional[str],
        data_loader: DataLoader,
        trading_api: Trader,
        max_share_price: float,
        min_share_price: float,
        min_last_dv: float,
        today_change_percent: float,
        min_volume: float,
        from_market_open: float,
        max_symbols: int = config.total_tickers,
        data_source: object = None,
    ):
        self.max_share_price = max_share_price
        self.min_share_price = min_share_price
        self.min_last_dv = min_last_dv
        self.min_volume = min_volume
        self.today_change_percent = today_change_percent
        self.from_market_open = from_market_open
        self.max_symbols = max_symbols
        self.trading_api = trading_api

        super().__init__(
            name=self.name,
            recurrence=recurrence,
            target_strategy_name=target_strategy_name,
            data_loader=data_loader,
            data_source=data_source,
        )

    @classmethod
    def __str__(cls) -> str:
        return cls.name

    async def _wait_time(self) -> None:
        if not config.bypass_market_schedule and config.market_open:
            nyc = timezone("America/New_York")
            since_market_open = (
                datetime.today().astimezone(nyc) - config.market_open
            )

            if since_market_open.seconds // 60 < self.from_market_open:
                tlog(f"market open, wait {self.from_market_open} minutes")
                while since_market_open.seconds // 60 < self.from_market_open:
                    await asyncio.sleep(1)
                    since_market_open = (
                        datetime.today().astimezone(nyc) - config.market_open
                    )

        tlog(f"Scanner {self.name} ready to run")

    async def _get_trade_able_symbols(self) -> List[str]:
        symbols = await self.trading_api.get_tradeable_symbols()
        tlog(f"loaded list of {len(symbols)} trade-able symbols from Alpaca")
        return symbols

    async def run_polygon(self) -> List[str]:
        tlog(f"{self.name}: run_polygon(): started")
        try:
            while True:
                tickers = self.data_loader.data_api.get_symbols()
                tlog(f"loaded {len(tickers)} tickers from Polygon")
                if not len(tickers):
                    break
                trade_able_symbols = await self._get_trade_able_symbols()

                unsorted = [
                    ticker
                    for ticker in tickers
                    if (
                        ticker["ticker"] in trade_able_symbols  # type: ignore
                        and self.max_share_price
                        >= ticker["lastTrade"]["p"]  # type: ignore
                        >= self.min_share_price  # type: ignore
                        and float(ticker["prevDay"]["v"])  # type: ignore
                        * float(ticker["lastTrade"]["p"])  # type: ignore
                        > self.min_last_dv  # type: ignore
                        and ticker["todaysChangePerc"]  # type: ignore
                        >= self.today_change_percent  # type: ignore
                        and (
                            ticker["day"]["v"] > self.min_volume  # type: ignore
                            or config.bypass_market_schedule
                        )
                    )
                ]
                if unsorted:
                    ticker_by_volume = sorted(
                        unsorted,
                        key=lambda ticker: float(ticker["day"]["v"]),  # type: ignore
                        reverse=True,
                    )
                    tlog(f"picked {len(ticker_by_volume)} symbols")
                    return [x["ticker"] for x in ticker_by_volume][  # type: ignore
                        : self.max_symbols
                    ]

                tlog("did not find gaping stock, retrying")
                await asyncio.sleep(30)
        except KeyboardInterrupt:
            tlog("KeyboardInterrupt")
        return []

    async def add_stock_data_for_date(self, symbol: str, when: date) -> None:
        _minute_data = self.data_loader[symbol][
            when : when + timedelta(days=1)  # type: ignore
        ]

        await asyncio.sleep(0)
        if _minute_data[symbol].empty:
            daily_bar = StockOhlc(
                symbol=symbol,
                symbol_date=when,
                open=0.0,
                high=0.0,
                low=0.0,
                close=0.0,
                volume=0,
                indicators={},
            )
            await daily_bar.save()
        else:
            for index, row in _minute_data[symbol].iterrows():
                daily_bar = StockOhlc(
                    symbol=symbol,
                    symbol_date=index,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=int(row["volume"]),
                    indicators={},
                )
                await daily_bar.save()
                print(f"saved data for {symbol} @ {index}")

    async def load_from_db(self, back_time: datetime) -> List[str]:
        pool = config.db_conn_pool

        daily_scale = back_time.hour == 0
        start = (
            back_time
            if daily_scale
            else back_time.replace(hour=9, minute=30, second=0, microsecond=0)
        )
        end = (
            back_time + timedelta(days=1)
            if daily_scale
            else back_time + timedelta(minutes=1)
        )
        async with pool.acquire() as con:
            rows = await con.fetch(
                """
                    SELECT
                        symbol
                    FROM 
                        trending_tickers
                    WHERE
                        scanner_name = $1 
                        AND create_tstamp >= $2
                        AND create_tstamp <= $3
                """,
                self.name,
                start,
                end,
            )

            print("load from db", start, end, len(rows))
            if len(rows) > 0:
                return [row[0] for row in rows]
            else:
                return []

    async def run(self, back_time: datetime = None) -> List[str]:
        if not back_time:
            await self._wait_time()
            return await self.run_polygon()
        else:
            rows = await self.load_from_db(back_time)

            print(
                f"Scanner {self.name} -> back_time={back_time} picked {len(rows)}"
            )
            return rows
