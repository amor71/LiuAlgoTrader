import asyncio
import concurrent.futures
import uuid
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
import numpy as np
from pandas import DataFrame as df
from scipy.stats import linregress
from stockstats import StockDataFrame
from tabulate import tabulate

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.market_data import index_data
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.miners.base import Miner
from liualgotrader.models.portfolio import Portfolio as DBPortfolio


class Trend(Miner):
    portfolio: df = df(columns=["symbol", "slope", "r", "score"])
    data_bars: Dict[str, df] = {}

    def __init__(
        self,
        data: Dict,
        debug=False,
    ):
        try:
            self.rank_days = int(data["rank_days"])
            self.atr_days = int(data["atr_days"])
            self.index = data["index"]
            self.debug = debug
            self.portfolio_size = data["portfolio_size"]
            self.risk_factor = data["risk_factor"]
            self.data_loader = DataLoader(TimeScale.day)

        except Exception:
            raise ValueError(
                "[ERROR] Miner must receive all valid parameter(s)"
            )
        super().__init__(name="PortfolioBuilder")

        if self.debug:
            tlog(f"{self.name} running in debug mode")

    def load_data_for_symbol(self, symbol: str) -> None:
        try:
            self.data_bars[symbol] = self.data_loader[symbol][
                date.today() - timedelta(days=int(200 * 7 / 5)) : date.today()  # type: ignore
            ]

            print(self.data_bars[symbol])
            if self.debug:
                try:
                    p_points = len(self.data_bars[symbol])
                except TypeError:
                    p_points = 0

                # tlog(f"loaded at least {p_points} relevant data-points")
        except Exception:
            tlog(f"[ERROR] could not load all data points for {symbol}")
            self.data_bars[symbol] = None

    async def load_data(self, symbols: List[str]) -> None:
        tlog("Data loading started")
        if not len(symbols):
            raise Exception(
                "load_data() received an empty list of symbols to load. aborting"
            )
        # We can use a with statement to ensure threads are cleaned up promptly
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Start the load operations and mark each future with its URL
            futures = {
                executor.submit(self.load_data_for_symbol, symbol): symbol
                for symbol in symbols
            }
            for _ in concurrent.futures.as_completed(futures):
                pass
        tlog(
            f"Data loading completed, loaded data for {len(self.data_bars)} symbols"
        )

    def calc_symbol_momentum(self, symbol: str) -> Optional[Dict]:
        d = self.data_bars[symbol]
        _df = df(d)
        deltas = np.log(_df.close[-self.rank_days :])
        slope, _, r_value, _, _ = linregress(np.arange(len(deltas)), deltas)
        if slope > 0:
            annualized_slope = (np.power(np.exp(slope), 252) - 1) * 100
            score = annualized_slope * (r_value ** 2)

            return dict(
                {
                    "symbol": symbol,
                    "slope": annualized_slope,
                    "r": r_value,
                    "score": score,
                },
            )
        else:
            return None

    async def calc_momentum(self) -> None:
        if not len(self.data_bars):
            raise Exception("calc_momentum() can't run without data. aborting")

        tlog("Trend ranking calculation started")
        symbols = [
            symbol
            for symbol in self.data_bars.keys()
            if not self.data_bars[symbol].empty
        ]

        l: List[Dict] = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Start the load operations and mark each future with its URL
            futures = {
                executor.submit(self.calc_symbol_momentum, symbol): symbol
                for symbol in symbols
            }
            for future in concurrent.futures.as_completed(futures):
                data = future.result()
                if data:
                    l.append(data)  # , ignore_index=True)

        self.portfolio = df.from_records(l).sort_values(
            by="score", ascending=False
        )
        tlog(
            f"Trend ranking calculation completed w/ {len(self.portfolio)} trending stocks"
        )

    def apply_filters_symbol(self, symbol: str) -> bool:
        indicator_calculator = StockDataFrame(self.data_bars[symbol])
        sma_100 = indicator_calculator["close_100_sma"]
        if self.data_bars[symbol].close[-1] < sma_100[-1]:
            return False

        # filter stocks moving > 15% in last 90 days
        high = self.data_bars[symbol].close[
            -1
        ]  # self.data_bars[row.symbol].close[-90:].max()
        low = self.data_bars[symbol].close[-90:].min()
        return high / low <= 1.25

    async def apply_filters(self) -> None:
        tlog("Applying filters")
        pre_filter_len = len(self.portfolio)
        symbols = [
            symbol
            for symbol in self.data_bars.keys()
            if not self.data_bars[symbol].empty
        ]

        pass_filter: list = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Start the load operations and mark each future with its URL
            futures = {
                executor.submit(self.apply_filters_symbol, symbol): symbol
                for symbol in symbols
            }
            for future in concurrent.futures.as_completed(futures):
                filter = future.result()
                if filter:
                    pass_filter.append(futures[future])

        self.portfolio = self.portfolio[
            self.portfolio.symbol.isin(pass_filter)
        ]
        tlog(f"filters removed {pre_filter_len-len(self.portfolio)}")

    async def calc_balance(self) -> None:
        # print("BEFORE ATR:")
        # print(f"\n{tabulate(self.portfolio, headers='keys', tablefmt='psql')}")
        for _, row in self.portfolio.iterrows():
            indicator_calculator = StockDataFrame(self.data_bars[row.symbol])
            indicator_calculator.ATR_SMMA = self.atr_days
            atr = indicator_calculator["atr"][-1]
            volatility = (
                self.data_bars[row.symbol]
                .close.pct_change()
                .rolling(20)
                .std()
                .iloc[-1]
            )
            qty = int(self.portfolio_size * self.risk_factor // volatility)
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "ATR"
            ] = atr
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "volatility"
            ] = volatility
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "qty"
            ] = qty
            self.portfolio.loc[self.portfolio.symbol == row.symbol, "est"] = (
                qty * self.data_bars[row.symbol].close[-1]
            )
        self.portfolio = self.portfolio.loc[self.portfolio.qty > 0]

    async def save_portfolio(self) -> str:
        portfolio_id = str(uuid.uuid4())
        tlog(f"Saving portfolio {portfolio_id}")
        await DBPortfolio.save(id=portfolio_id, df=self.portfolio)
        tlog("Done.")
        return portfolio_id

    async def execute_portfolio(self) -> None:
        self.portfolio["accumulative"] = self.portfolio.est.cumsum()

        if self.debug:
            print(
                f"FINAL:\n{tabulate(self.portfolio, headers='keys', tablefmt='psql')}"
            )

    async def run(self) -> bool:
        symbols = (await index_data(self.index)).Symbol.tolist()

        if self.debug:
            tlog(f"Index {self.index} symbols: {symbols}")

        await self.load_data(symbols)

        await self.calc_momentum()

        await self.apply_filters()

        await self.calc_balance()

        portfolio_id = await self.save_portfolio()

        await self.execute_portfolio()

        print(
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
        )
        tlog(f"PORTFOLIO_ID:{portfolio_id}")
        print(
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
        )

        return True
