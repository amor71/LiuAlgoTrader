"""
    Find short-able, liquid, large-cap stocks that gap down.
    Inspired by https://www.quantrocket.com/blog/buy-or-sell-down-gaps/

    NOTE: the SMA criteria should be implemented as a buy signal (if really needed)
        by the strategy
"""

import asyncio
import statistics
from datetime import date, datetime, timedelta
from typing import List, Optional

import alpaca_trade_api as tradeapi
from liualgotrader.common import config
from liualgotrader.common.market_data import get_historical_data_from_polygon_by_range
from liualgotrader.common.tlog import tlog
from liualgotrader.scanners.base import Scanner
from pytz import timezone


class GapDown(Scanner):
    name = "GapDown"

    def __init__(
        self,
        data_api: tradeapi,
        recurrence: Optional[timedelta] = None,
        target_strategy_name: str = None,
        max_symbols: int = config.total_tickers,
    ):
        self.max_symbols = max_symbols
        super().__init__(
            name=self.name,
            recurrence=recurrence,
            target_strategy_name=target_strategy_name,
            data_api=data_api,
        )

    async def _wait_time(self) -> None:
        if not config.bypass_market_schedule and config.market_open:
            nyc = timezone("America/New_York")
            since_market_open = datetime.today().astimezone(nyc) - config.market_open

            if since_market_open.seconds // 60 < 10:
                tlog(f"{self.name} market open, wait {10} minutes")
                while since_market_open.seconds // 60 < 10:
                    await asyncio.sleep(1)
                    since_market_open = (
                        datetime.today().astimezone(nyc) - config.market_open
                    )

        tlog(f"Scanner {self.name} ready to run")

    def _get_short_able_trade_able_symbols(self) -> List[str]:
        assets = self.data_api.list_assets()
        tlog(
            f"{self.name} -> loaded list of {len(assets)} trade-able assets from Alpaca"
        )

        trade_able_symbols = [
            asset.symbol
            for asset in assets
            if asset.tradable and asset.shortable and asset.easy_to_borrow
        ]
        tlog(f"total number of trade-able symbols is {len(trade_able_symbols)}")
        return trade_able_symbols

    async def run(self) -> List[str]:
        tlog(f"{self.name}: run(): started")
        await self._wait_time()

        try:
            tickers = self.data_api.polygon.all_tickers()
            tlog(f"{self.name} -> loaded {len(tickers)} tickers from Polygon")
            if not len(tickers):
                return []

            trade_able_symbols = self._get_short_able_trade_able_symbols()
            unsorted = [
                ticker
                for ticker in tickers
                if (
                    ticker.ticker in trade_able_symbols
                    and ticker.lastTrade["p"] >= 20.0
                    and ticker.prevDay["v"] * ticker.lastTrade["p"] > 500000.0
                    and ticker.prevDay["l"] > ticker.day["o"]
                    and ticker.todaysChangePerc < 0
                    and (ticker.day["v"] > 30000.0 or config.bypass_market_schedule)
                )
            ]

            if len(unsorted):
                symbols = [ticker.ticker for ticker in unsorted]
                _daiy_data = get_historical_data_from_polygon_by_range(
                    self.data_api,
                    symbols,
                    date.today() - timedelta(days=30),
                    "day",
                )
                std = {}
                for symbol in symbols:
                    if symbol in _daiy_data:
                        std[symbol] = statistics.pstdev(_daiy_data[symbol]["low"])

                unsorted = [
                    x
                    for x in unsorted
                    if x.ticker in symbols
                    and x.day["o"] < (x.prevDay["l"] - std[x.ticker])
                ]

                if len(unsorted) > 0:
                    ticker_by_volume = sorted(
                        unsorted,
                        key=lambda ticker: float(ticker.day["v"]),
                        reverse=True,
                    )
                    r_symbols = [x.ticker for x in ticker_by_volume][: self.max_symbols]
                    tlog(f"{self.name} -> picked {len(r_symbols)} symbols {r_symbols}")
                    return r_symbols

            tlog(f"{self.name} -> did not find gaping down stocks, sorry..")

        except KeyboardInterrupt:
            tlog("KeyboardInterrupt")
            pass
        except Exception as e:
            print(e)

        return []
