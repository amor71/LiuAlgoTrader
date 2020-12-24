import sys
import traceback
from typing import Dict, List

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.common.market_data import daily_bars, index_tickers
from liualgotrader.common.tlog import tlog
from liualgotrader.miners.base import Miner


class Portfolio(Miner):
    portfolio: df
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
            self.data_api = tradeapi.REST(
                base_url=config.prod_base_url,
                key_id=config.prod_api_key_id,
                secret_key=config.prod_api_secret,
            )

        except Exception:
            raise ValueError("[ERROR] Miner must receive valid parameters")
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
                    f"loading {self.rank_days} days for symbol {symbol} ({i}/{len(symbols)}"
                )
            self.data_bars[symbol] = daily_bars(
                api=self.data_api,
                symbol=symbol,
                days=int(self.rank_days * 7 / 5),
            )
            if self.debug:
                tlog(f"loaded {len(self.data_bars[symbol])} data-points")
            i += 1

    async def calc_momentum(self) -> None:
        if not len(self.data_bars):
            raise Exception("calc_momentum() can't run without data. aborting")

        for symbol, d in self.data_bars.items():
            d["delta"] = df.close.diff().shift(-1)
            print(d)

    async def run(self) -> bool:
        symbols = await index_tickers(self.index)

        if self.debug:
            tlog(f"Index {self.index} symbols: {symbols}")

        await self.load_data(symbols)

        await self.calc_momentum()

        return True

        await self.apply_filters()

        await self.calc_balance()

        await self.save_portfolio()

        return True
