import uuid
from typing import Dict, List

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df
from scipy.stats import linregress
from stockstats import StockDataFrame

from liualgotrader.common import config
from liualgotrader.common.market_data import daily_bars, index_data
from liualgotrader.common.tlog import tlog
from liualgotrader.miners.base import Miner
from liualgotrader.models.portfolio import Portfolio as DBPortfolio


class Portfolio(Miner):
    portfolio: df = df(columns=["symbol", "slope", "r", "ranked_slope"])
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
            self.indicators = data["indicators"]
            self.debug = debug
            self.portfolio_size = data["portfolio_size"]
            self.risk_factor = data["risk_factor"]
            self.data_api = tradeapi.REST(
                base_url=config.prod_base_url,
                key_id=config.prod_api_key_id,
                secret_key=config.prod_api_secret,
            )

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

        i = 1
        for symbol in symbols:
            if self.debug:
                tlog(
                    f"loading 200 days for symbol {symbol} ({i}/{len(symbols)})"
                )
            self.data_bars[symbol] = daily_bars(
                api=self.data_api,
                symbol=symbol,
                days=int(200 * 7 / 5),
            )
            if self.debug:
                tlog(f"loaded {len(self.data_bars[symbol])} data-points")
            i += 1

    async def calc_momentum(self) -> None:
        if not len(self.data_bars):
            raise Exception("calc_momentum() can't run without data. aborting")

        i = 0
        for symbol, d in self.data_bars.items():
            d["delta"] = d.close.pct_change()
            d = d.dropna()

            deltas = d.delta.tolist()[-self.rank_days :]
            slope, intercept, r, _, _ = linregress(range(len(deltas)), deltas)
            i += 1
            if slope > 0:
                if self.debug:
                    tlog(
                        f"{symbol}({i}/{len(self.data_bars.keys())}) slope:{slope} r:{r} ({len(deltas)} days)"
                    )
                self.portfolio = self.portfolio.append(
                    {
                        "symbol": symbol,
                        "slope": slope,
                        "r": r,
                        "ranked_slope": slope * r,
                    },
                    ignore_index=True,
                )

        self.portfolio = self.portfolio.sort_values(
            by="ranked_slope", ascending=False
        )

    async def apply_filters(self) -> None:
        c = 0
        d = df(self.portfolio)
        for i, row in self.portfolio.iterrows():
            indicator_calculator = StockDataFrame(self.data_bars[row.symbol])

            c += 1
            removed = False
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
                        removed = True

            # filter stocks moving > 15% in last 90 days
            high = self.data_bars[row.symbol].close[-90:].max()
            low = self.data_bars[row.symbol].close[-90:].min()
            if not removed and high / low > 1.15:
                if self.debug:
                    tlog(
                        f"{row.symbol} ({c}/{len(self.portfolio)}) REMOVED on movement ({high},{low})> 15% in last 90 days"
                    )
                    d = d.drop(index=i)
                    removed = True

        self.portfolio = d

    async def calc_balance(self) -> None:
        for i, row in self.portfolio.iterrows():
            indicator_calculator = StockDataFrame(self.data_bars[row.symbol])
            indicator_calculator.ATR_SMMA = 20
            atr = indicator_calculator["atr"][-1]
            qty = int(self.portfolio_size * self.risk_factor // atr)
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "ATR"
            ] = atr
            self.portfolio.loc[
                self.portfolio.symbol == row.symbol, "qty"
            ] = qty
            self.portfolio.loc[self.portfolio.symbol == row.symbol, "est"] = (
                qty * self.data_bars[row.symbol].close[-1]
            )
        self.portfolio = self.portfolio.loc[self.portfolio.qty > 0]

    async def save_portfolio(self) -> str:
        portfolio_id = str(uuid.uuid4())
        await DBPortfolio.save(id=portfolio_id, df=self.portfolio)
        return portfolio_id

    async def run(self) -> bool:
        symbols = (await index_data(self.index)).Symbol.tolist()

        if self.debug:
            tlog(f"Index {self.index} symbols: {symbols}")

        await self.load_data(symbols)

        await self.calc_momentum()

        await self.apply_filters()

        await self.calc_balance()

        if self.debug:
            tlog(f"{self.portfolio}")
            tlog(
                f"total to invest = {min(self.portfolio_size, self.portfolio.est.sum())}"
            )

        portfolio_id = await self.save_portfolio()
        print(
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
        )
        tlog(f"PORTFOLIO_ID:{portfolio_id}")
        print(
            "-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-="
        )

        return True
