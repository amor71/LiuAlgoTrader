from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from liualgotrader.common import config
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
    name = "MyStrategyForLosingMoney"

    def __init__(
        self,
        batch_id: str,
        schedule: List[Dict],
        ref_run_id: int = None,
        my_arg1: int = 0,
        my_arg2: bool = False,
    ):
        super().__init__(
            name=self.name,
            batch_id=batch_id,
            ref_run_id=ref_run_id,
            schedule=schedule,
            type=StrategyType.DAY_TRADE,
        )
        self.my_arg1 = my_arg1
        self.my_arg2 = my_arg2

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        """
        This callback function is called by the trading frame work post
        completion of the buy ask. Partial fills won't trigger the callback,
        only the final complete will trigger this callback.
        """
        pass

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        """
        This callback function is called by the trading frame work post
        completion of the sell ask. Partial fills won't trigger the callback,
        only the final complete will trigger this callback.
        """
        pass

    async def create(self) -> None:
        """
        This function is called by the framework during the instantiation
        of the strategy. Keep in mind that running on multi-process environment
        it means that this function will be called at least once per spawned process.
        :return:
        """
        await super().create()
        tlog(f"strategy {self.name} created")

    async def run(
        self,
        symbol: str,
        shortable: bool,
        position: int,
        minute_history: df,
        now: datetime,
        portfolio_value: float = None,
        trading_api: tradeapi = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        """

        :param symbol: the symbol of the stock,
        :param shortable: can the stock be sold short,
        :param position: the current held position,
        :param minute_history: DataFrame holding OLHC
                               updated per *second*,
        :param now: current timestamp, specially important when called
                    from the backtester application,
        :param portfolio_value: your total porfolio value
        :param trading_api: the Alpca tradeapi, may either be
                            paper or live, depending on the
                            environment variable configurations,
        :param debug:       true / false, should be used mostly
                            for adding more verbosity.
        :param backtesting: true / false, which more are we running at
        :return: False w/ {} dictionary, or True w/ order execution
                 details (see below examples)
        """
        current_second_data = minute_history.iloc[-1]
        tlog(f"{symbol} data: {current_second_data}")

        morning_rush = (
            True if (now - config.market_open).seconds // 60 < 30 else False
        )
        if await super().is_buy_time(now) and not position:
            # Check for buy signals
            lbound = config.market_open
            ubound = lbound + timedelta(minutes=15)

            if debug:
                tlog(f"15 schedule {lbound}/{ubound}")
            try:
                high_15m = minute_history[lbound:ubound]["high"].max()  # type: ignore
                if debug:
                    tlog(f"{minute_history[lbound:ubound]}")  # type: ignore
            except Exception as e:
                return False, {}

            if (
                current_second_data.close > high_15m
                or config.bypass_market_schedule
            ):

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
                    }
                    if not morning_rush
                    else {
                        "side": "buy",
                        "qty": str(5),
                        "type": "market",
                    },
                )
        if (
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
