import uuid
from datetime import date, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import numpy as np
from pandas import DataFrame as df
from scipy.stats import linregress
from stockstats import StockDataFrame
from tabulate import tabulate
from talib import BBANDS, MACD, RSI, MA_Type

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.market_data import index_data
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.miners.base import Miner
from liualgotrader.models.portfolio import Portfolio as DBPortfolio


class Pullback(Miner):
    portfolio: df = df(columns=["symbol", "slope", "r", "score"])
    data_bars: Dict[str, df] = {}

    def __init__(
        self,
        data: Dict,
        debug=False,
    ):
        try:
            self.rank_days = int(data["rank_days"])
            self.index = data["index"]
            self.indicators = data["indicators"]
            self.debug = debug
            self.portfolio_size = data["portfolio_size"]
            self.risk_factor = data["risk_factor"]
            self.data_loader = DataLoader(TimeScale.day)
            self.pullback_days = data["pullback_days"]
        except Exception:
            raise ValueError(
                "[ERROR] Miner must receive all valid parameter(s)"
            )
        super().__init__(name="PortfolioBuilder")

        if self.debug:
            tlog(f"{self.name} running in debug mode")

    async def load_data(self, symbols: List[str]) -> None:
        if not len(symbols):
            raise Exception(
                "load_data() received an empty list of symbols to load. aborting"
            )

        for i, symbol in enumerate(symbols, start=1):
            if self.debug:
                tlog(
                    f"loading 200 days for symbol {symbol} ({i}/{len(symbols)})"
                )
            try:
                self.data_bars[symbol] = self.data_loader[symbol][
                    date.today() - timedelta(days=int(200 * 7 / 5)) : date.today()  # type: ignore
                ]
                if self.debug:
                    try:
                        p_points = len(self.data_bars[symbol])
                    except TypeError:
                        p_points = 0

                    tlog(f"loaded at least {p_points} relevant data-points")
            except Exception:
                tlog(f"[ERROR] could not load all data points for {symbol}")
                self.data_bars[symbol] = None

    async def calc_momentum(self) -> None:
        if not len(self.data_bars):
            raise Exception("calc_momentum() can't run without data. aborting")

        for i, (symbol, d) in enumerate(self.data_bars.items(), start=1):
            if d is None or d.empty:
                continue
            _df = df(d)
            deltas = np.log(_df.close[-self.rank_days :])
            slope, _, r_value, _, _ = linregress(
                np.arange(len(deltas)), deltas
            )
            if slope > 0:
                annualized_slope = (np.power(np.exp(slope), 252) - 1) * 100
                score = annualized_slope * (r_value ** 2)
                if self.debug:
                    tlog(
                        f"{symbol}({i}/{len(self.data_bars.keys())}) slope:{slope} annualized_slope:{annualized_slope} r:{r_value} ({len(deltas)} days)"
                    )
                self.portfolio = self.portfolio.append(
                    {
                        "symbol": symbol,
                        "slope": annualized_slope,
                        "r": r_value,
                        "score": score,
                    },
                    ignore_index=True,
                )

        self.portfolio = self.portfolio.sort_values(
            by="score", ascending=False
        )

    async def apply_filters(self) -> None:
        d = df(self.portfolio)
        for c, (i, row) in enumerate(self.portfolio.iterrows(), start=1):
            indicator_calculator = StockDataFrame(self.data_bars[row.symbol])

            for indicator in self.indicators:
                if indicator == "SMA100":
                    sma_100 = indicator_calculator["close_100_sma"]

                    if self.debug:
                        tlog(
                            f"indicator {indicator} for {row.symbol} ({c}/{len(self.portfolio)}) : {sma_100[-1]}"
                        )

                    if self.data_bars[row.symbol].close[-1] < sma_100[-1]:
                        if self.debug:
                            tlog(f"{row.symbol} REMOVED on SMA")

                        d = d.drop(index=i)

        self.portfolio = d

    async def calc_pullback(self) -> None:
        for i, row in self.portfolio.iterrows():
            # print(row.symbol, len(self.data_bars[row.symbol]))

            bband = BBANDS(
                self.data_bars[row.symbol].close,
                timeperiod=7,
                nbdevdn=1,
                nbdevup=1,
                matype=MA_Type.EMA,
            )

            lower_band = bband[2]
            upper_band = bband[0]

            volatility = upper_band[-1] - lower_band[-1]

            position = 0
            profit = 0.0
            count = 0
            for i in range(-self.pullback_days, -1, 1):
                if (
                    not position
                    and self.data_bars[row.symbol].close[i - 1]
                    < lower_band[i - 1]
                    and self.data_bars[row.symbol].close[i]
                    > self.data_bars[row.symbol].close[i - 1]
                    and self.data_bars[row.symbol].close[i] > lower_band[i]
                ):
                    position = (
                        self.portfolio_size
                        // self.data_bars[row.symbol].open[i]
                    )
                    profit -= position * self.data_bars[row.symbol].open[i]
                    count += 1
                elif (
                    position
                    and self.data_bars[row.symbol].open[i] > upper_band[i - 1]
                ):
                    profit += position * self.data_bars[row.symbol].open[i]
                    position = 0

            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "count"
            ] = count
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "profit"
            ] = profit
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "volatility"
            ] = volatility
            qty = int(count * self.risk_factor / volatility)
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "qty"
            ] = qty
            self.portfolio.loc[self.portfolio.symbol == row.symbol, "est"] = (
                qty * self.data_bars[row.symbol].close[-1]
            )
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "opt"
            ] = bool(self.data_bars[row.symbol].close[-1] < lower_band[-1])
        self.portfolio = self.portfolio.loc[
            (self.portfolio.profit > 0)
            & (self.portfolio.opt == True)
            & (self.portfolio.volatility > 2.0)
            & (self.portfolio.score > 35.0)
        ]

    async def save_portfolio(self) -> str:
        portfolio_id = str(uuid.uuid4())
        await DBPortfolio.save(id=portfolio_id, df=self.portfolio)
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

        await self.calc_pullback()

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
