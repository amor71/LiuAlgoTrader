from datetime import datetime, timedelta
from typing import Dict, Tuple

import alpaca_trade_api as tradeapi
import numpy as np
from google.cloud import error_reporting
from pandas import DataFrame as df
from talib import BBANDS, MACD, RSI

from common import config
from common.tlog import tlog
from common.trading_data import (buy_indicators, cool_down, latest_cost_basis,
                                 sell_indicators, stop_prices,
                                 symbol_resistance, target_prices)

from .base import Strategy

error_logger = error_reporting.Client()


class VWAPLong(Strategy):
    name = "vwap_long"

    def __init__(self, batch_id: str):
        super().__init__(name=self.name, batch_id=batch_id)

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_cost_basis[symbol] = price

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_cost_basis[symbol] = price

    async def create(self) -> None:
        await super().create()
        tlog(f"strategy {self.name} created")

    async def run(
        self,
        symbol: str,
        position: int,
        minute_history: df,
        now: datetime,
        portfolio_value: float = None,
        trading_api: tradeapi = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        data = minute_history.iloc[-1]
        prev_minute = minute_history.iloc[-2]
        prev_two_minute = minute_history.iloc[-3]
        prev_three_minute = minute_history.iloc[-4]
        if await super().is_buy_time(now) and not position:
            # print(
            #    symbol,
            #    data.close,
            #    data.average,
            #    prev_minute.close,
            #    prev_minute.average,
            #    prev_two_minute.close,
            #    prev_two_minute.average,
            # )
            if (
                data.close
                > prev_minute.close
                > prev_two_minute.close
                > prev_three_minute.close
                and data.close > data.average
                and prev_minute.close > prev_minute.average
                and prev_two_minute.close > prev_two_minute.average
                and prev_three_minute.close < prev_three_minute.average
            ):
                tlog(
                    f"{symbol} found conditions for VWAP strategy now:{data}, prev_min:{prev_minute}, prev_2min:{prev_two_minute}"
                )
                upperband, middleband, lowerband = BBANDS(
                    minute_history["close"], timeperiod=20,
                )

                stop_prices[symbol] = lowerband[-1]
                target_prices[symbol] = upperband[-1]

                if portfolio_value is None:
                    if trading_api:
                        portfolio_value = float(
                            trading_api.get_account().portfolio_value
                        )
                    else:
                        raise Exception(
                            "VWAPLong.run(): both portfolio_value and trading_api can't be None"
                        )

                shares_to_buy = (
                    portfolio_value
                    * config.risk
                    // (data.close - stop_prices[symbol])
                )
                if not shares_to_buy:
                    shares_to_buy = 1
                shares_to_buy -= position

                if shares_to_buy > 0:
                    tlog(
                        f"[{self.name}] Submitting buy for {shares_to_buy} shares of {symbol} at {data.close} target {target_prices[symbol]} stop {stop_prices[symbol]}"
                    )
                    buy_indicators[symbol] = {
                        "bbrand_lower": lowerband[-5:].tolist(),
                        "bbrand_middle": middleband[-5:].tolist(),
                        "bbrand_upper": upperband[-5:].tolist(),
                    }

                    return (
                        True,
                        {
                            "side": "buy",
                            "qty": str(shares_to_buy),
                            "type": "limit",
                            "limit_price": str(data.close),
                        },
                    )

        return False, {}
