import math
from datetime import date, timedelta
from typing import Dict, List, Optional

import alpaca_trade_api as tradeapi
from talib import MAMA

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
        symbols: Optional[List[str]],
        debug=False,
    ):
        self._num_workers = 20
        self._days = days
        self._min_stock_price = min_stock_price
        self._max_stock_price = max_stock_price
        self._indicators = indicators
        self._symbols = symbols
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

    @property
    def symbols(self) -> Optional[List[str]]:
        return self._symbols

    @symbols.setter
    def symbols(self, symbols: Optional[List[str]]) -> None:
        self._symbols = symbols

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

        if symbol in _minute_data:
            for index, row in _minute_data[symbol].iterrows():
                indicators: Dict = {}
                if self.indicators:
                    for indicator in self.indicators:
                        if indicator == "mama":
                            mama, fama = MAMA(
                                _minute_data[symbol]["close"][:index].dropna()
                            )
                            indicators["mama"] = (
                                mama[-1] if not math.isnan(mama[-1]) else None
                            )
                            indicators["fama"] = (
                                fama[-1] if not math.isnan(fama[-1]) else None
                            )

                daily_bar = StockOhlc(
                    symbol=symbol,
                    symbol_date=index,
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=int(row["volume"]),
                    indicators=indicators,
                )
                await daily_bar.save()

            tlog(f"saved {len(_minute_data[symbol].index)} days for {symbol}")

    @timeit
    async def run(self) -> bool:

        if not self.symbols:
            self.symbols = await TickerData.load_symbols()

        if not self.symbols:
            return False

        # check last date
        for symbol in self.symbols:
            latest_date = await StockOhlc.get_latest_date(symbol)

            if self._debug:
                tlog(f"{symbol} latest date: {latest_date}")

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

        return True
