import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from json.decoder import JSONDecodeError
from typing import Dict, List, Optional

import alpaca_trade_api as tradeapi
import requests
from alpaca_trade_api.common import get_polygon_credentials
from alpaca_trade_api.polygon.entity import Ticker

from liualgotrader.common import config
from liualgotrader.common.decorators import timeit
from liualgotrader.common.market_data import \
    get_historical_data_from_polygon_by_range
from liualgotrader.common.tlog import tlog
from liualgotrader.miners.base import Miner
from liualgotrader.models.ticker_data import StockOhlc, TickerData


class DailyOHLC(Miner):
    def __init__(
        self,
        days: int,
        min_stock_price: Optional[float],
        max_stock_price: Optional[float],
        indicators: Optional[Dict],
        debug=False,
    ):
        self._num_workers = 20
        self._days = days
        self._min_stock_price = min_stock_price
        self._max_stock_price = max_stock_price
        self._indicators = indicators
        self._debug = debug
        self.data_api = tradeapi.REST(
            base_url=config.prod_base_url,
            key_id=config.prod_api_key_id,
            secret_key=config.prod_api_secret,
        )
        super().__init__(name="DailyOHLC")

    @property
    def days(self) -> int:
        return self._days

    @property
    def min_stock_price(self) -> Optional[float]:
        return self._min_stock_price

    @property
    def max_stock_price(self) -> Optional[float]:
        return self._max_stock_price

    @property
    def indicators(self) -> Optional[Dict]:
        return self._indicators

    @timeit
    async def load_symbol_data(
        self,
        symbol: str,
        days: int,
    ) -> None:
        start_date = date.today() - timedelta(days=days)
        _minute_data = get_historical_data_from_polygon_by_range(
            self.data_api, [symbol], start_date, "day"
        )

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

        tlog(f"saved {len(_minute_data[symbol].index)} days for {symbol}")

    @timeit
    async def run(self) -> bool:
        symbols = await TickerData.load_symbols()

        if not symbols:
            return False

        # check last date
        for symbol in symbols:
            latest_date = await StockOhlc.get_latest_date(symbol)

            if not latest_date:
                if self._debug:
                    tlog(f"{symbol} loading {self.days} of OHLC data")
                await self.load_symbol_data(symbol, self.days)
            else:
                latest_date += timedelta(days=1)
                duration = min(self.days, (date.today() - latest_date).days)

                if self._debug:
                    tlog(f"{symbol} loading {duration} of OHLC data")
                await self.load_symbol_data(symbol, duration)

            # get OLHC

            # calculate indicator

        return True
