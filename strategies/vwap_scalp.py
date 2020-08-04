from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
import pandas as pd
import talib
from google.cloud import error_reporting
from pandas import DataFrame as df
from pandas import Series
from pandas import Timestamp as ts
from pandas import concat
from tabulate import tabulate
from talib import BBANDS, MACD, RSI

from common import config
from common.tlog import tlog
from common.trading_data import (buy_indicators, down_cross,
                                 last_used_strategy, latest_cost_basis,
                                 open_orders, sell_indicators, stop_prices,
                                 target_prices)
from fincalcs.candle_patterns import doji
from fincalcs.support_resistance import find_stop
from fincalcs.vwap import add_daily_vwap

from .base import Strategy

error_logger = error_reporting.Client()


class VWAPScalp(Strategy):
    name = "vwap_scalp"

    def __init__(self, batch_id: str, ref_run_id: int = None):
        super().__init__(
            name=self.name, batch_id=batch_id, ref_run_id=ref_run_id
        )

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_cost_basis[symbol] = price

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_cost_basis[symbol] = price

    async def create(self) -> None:
        await super().create()
        tlog(f"strategy {self.name} created")

    # async def is_buy_time(self, now: datetime):
    #    return (
    #        True
    #        if 45
    #        > (now - config.market_open).seconds // 60
    #        > config.market_cool_down_minutes
    #        or config.bypass_market_schedule
    #        else False
    #    )

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
        prev_2minutes = minute_history.iloc[-3]

        if await self.is_buy_time(now) and not position:
            # Check for buy signals
            if backtesting:
                back_time = ts(config.market_open)
                back_time_index = minute_history["close"].index.get_loc(
                    back_time, method="nearest"
                )
                close = (
                    minute_history["close"][back_time_index:-1]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                open = (
                    minute_history["open"][back_time_index:-1]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                high = (
                    minute_history["high"][back_time_index:-1]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                low = (
                    minute_history["low"][back_time_index:-1]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                volume = (
                    minute_history["volume"][back_time_index:-1]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                _df = concat(
                    [
                        open.rename("open"),
                        high.rename("high"),
                        low.rename("low"),
                        close.rename("close"),
                        volume.rename("volume"),
                    ],
                    axis=1,
                )

                if not add_daily_vwap(_df):
                    tlog(f"[{now}]failed add_daily_vwap")
                    return False, {}

                if debug:
                    tlog(
                        f"\n[{now}]{symbol} {tabulate(_df[-10:], headers='keys', tablefmt='psql')}"
                    )
                vwap_series = _df["average"]

                if debug:
                    tlog(
                        f"[{now}] {symbol} close:{round(data.close,2)} vwap:{round(vwap_series[-1],2)}"
                    )
            else:
                vwap_series = minute_history["average"]

            if len(vwap_series) < 3:
                tlog(f"[{now}]{symbol}: missing vwap values {vwap_series}")
                return False, {}

            if (
                prev_2minutes.close > vwap_series[-3]
                and prev_minute.close < vwap_series[-2]
            ):
                down_cross[symbol] = minute_history.index[-3].to_pydatetime()

            if (
                data.low > vwap_series[-1]
                and data.vwap > data.open
                and data.close > prev_minute.close > vwap_series[-2]
                and prev_2minutes.low < vwap_series[-3]
            ):

                if not symbol in down_cross:
                    tlog(
                        f"[{now}] {symbol} did not find download crossing in the past 15 min"
                    )
                    return False, {}
                if minute_history.index[-1].to_pydatetime() - down_cross[
                    symbol
                ] >= timedelta(minutes=15):
                    tlog(
                        f"[{now}] {symbol} down-crossing too far {down_cross[symbol]} from now"
                    )
                    return False, {}
                stop_price = find_stop(
                    data.close if not data.vwap else data.vwap,
                    minute_history,
                    now,
                )
                target = data.close + 0.03

                stop_prices[symbol] = stop_price
                target_prices[symbol] = target

                tlog(
                    f"{symbol} found conditions for VWAP-Scalp strategy now:{now}"
                )

                tlog(
                    f"\n{tabulate(minute_history[-10:], headers='keys', tablefmt='psql')}"
                )

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
                    * 20.0
                    * config.risk
                    // data.close
                    # // (data.close - stop_prices[symbol])
                )
                if not shares_to_buy:
                    shares_to_buy = 1
                shares_to_buy -= position

                if shares_to_buy > 0:
                    tlog(
                        f"[{self.name}] Submitting buy for {shares_to_buy} shares of {symbol} at {data.close} target {target_prices[symbol]} stop {stop_prices[symbol]}"
                    )
                    buy_indicators[symbol] = {
                        "average": round(data.average, 2),
                        "vwap": round(data.vwap, 2),
                        "patterns": None,
                    }

                    return (
                        True,
                        {
                            "side": "buy",
                            "qty": str(shares_to_buy),
                            "type": "limit",
                            "limit_price": str(data.close + 0.01),
                        },
                    )

        elif (
            await super().is_sell_time(now)
            and position > 0
            and symbol in latest_cost_basis
            and last_used_strategy[symbol].name == self.name
        ):
            if open_orders.get(symbol) is not None:
                tlog(f"vwap_scalp: open order for {symbol} exists, skipping")
                return False, {}

            to_sell = False
            to_sell_market = False
            if data.vwap <= data.average - 0.05:
                to_sell = True
                reason = "below VWAP"
                to_sell_market = True
            elif data.close >= target_prices[symbol]:
                to_sell = True
                reason = "vwap scalp"

            if to_sell:
                sell_indicators[symbol] = {
                    "reason": reason,
                    "average": data.average,
                    "vwap": data.vwap,
                }
                return (
                    True,
                    {"side": "sell", "qty": str(position), "type": "market"}
                    if to_sell_market
                    else {
                        "side": "sell",
                        "qty": str(position),
                        "type": "limit",
                        "limit_price": str(data.close),
                    },
                )

        return False, {}


"""
            elif doji(data.open, data.close, data.high, data.low):
                sell_indicators[symbol] = {
                    "reason": "doji",
                    "average": data.average,
                    "vwap": data.vwap,
                }
                return (
                    True,
                    {"side": "sell", "qty": str(position), "type": "market",},
                )
"""
