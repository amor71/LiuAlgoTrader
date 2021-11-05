from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
import pandas as pd
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.tlog import tlog
#
# common.trading_data includes global variables, cross strategies that may be
# helpful
#
from liualgotrader.common.trading_data import (buy_indicators,
                                               last_used_strategy, open_orders,
                                               sell_indicators, stop_prices,
                                               target_prices)
from liualgotrader.strategies.base import Strategy, StrategyType

#
# TALIB is *NOT* available as part of LiuAlgoTrader distribution,
# though it's highly recommended.
# Dcumentation can be found here https://www.ta-lib.org/
#
# import talib
# from talib import BBANDS, MACD, RSI


class MyStrategy(Strategy):
    def __init__(
        self,
        batch_id: str,
        schedule: List[Dict],
        data_loader: DataLoader = None,
        fractional: bool = False,
        ref_run_id: int = None,
        my_arg1: int = 0,
        my_arg2: bool = False,
    ):
        super().__init__(
            name=type(self).__name__,
            type=StrategyType.SWING,
            batch_id=batch_id,
            ref_run_id=ref_run_id,
            schedule=[],
            data_loader=data_loader,
        )
        self.my_arg1 = my_arg1
        self.my_arg2 = my_arg2

    async def buy_callback(
        self,
        symbol: str,
        price: float,
        qty: float,
        now: datetime = None,
        trade_fee: float = 0.0,
    ) -> None:
        ...

    async def sell_callback(
        self,
        symbol: str,
        price: float,
        qty: float,
        now: datetime = None,
        trade_fee: float = 0.0,
    ) -> None:
        ...

    async def create(self) -> bool:
        """
        This function is called by the framework during the instantiation
        of the strategy. Keep in mind that running on multi-process environment
        it means that this function will be called at least once per spawned process.
        :return:
        """
        await super().create()
        tlog(f"strategy {self.name} created")
        return True

    async def should_run_all(self):
        return False

    async def run(
        self,
        symbol: str,
        shortable: bool,
        position: float,
        now: datetime,
        minute_history: pd.DataFrame,
        portfolio_value: float = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        current_second_data = minute_history.iloc[-1]
        tlog(f"{symbol} data: {current_second_data}")

        if await super().is_buy_time(now) and not position:
            #
            # Check for buy signals??
            #

            #
            # Global, cross strategies passed via the framework
            #
            target_prices[symbol] = 15.0
            stop_prices[symbol] = 3.8

            #
            # indicators *should* be filled
            #
            buy_indicators[symbol] = {"my_indicator": "random"}

            return (
                True,
                {
                    "side": "buy",
                    "qty": str(10),
                    "type": "limit",
                    "limit_price": "4.4",
                },
            )
        elif (
            await super().is_sell_time(now)
            and position > 0
            and last_used_strategy[symbol].name == self.name  # important!
        ):
            # check if we already have open order
            if open_orders.get(symbol) is not None:
                tlog(f"{self.name}: open order for {symbol} exists, skipping")
                return False, {}

            # Check for liquidation signals
            sell_indicators[symbol] = {"my_indicator": "random"}

            tlog(
                f"[{self.name}] Submitting sell for {position} shares of {symbol} at {current_second_data.close}"
            )
            return (
                True,
                {
                    "side": "sell",
                    "qty": str(position),
                    "type": "limit",
                    "limit_price": str(current_second_data.close),
                },
            )

        return False, {}
