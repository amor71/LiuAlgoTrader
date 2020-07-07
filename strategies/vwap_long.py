from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
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
from common.trading_data import (buy_indicators, last_used_strategy,
                                 latest_cost_basis, sell_indicators,
                                 stop_prices, target_prices)
from fincalcs.candle_patterns import doji
from fincalcs.vwap import add_daily_vwap

from .base import Strategy

error_logger = error_reporting.Client()


class VWAPLong(Strategy):
    name = "vwap_long"

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
            # Check for buy signals
            lbound = config.market_open
            ubound = lbound + timedelta(minutes=16)
            try:
                high_15m = minute_history[lbound:ubound][  # type: ignore
                    "high"
                ].max()

                if data.vwap < high_15m:
                    return False, {}
            except Exception as e:
                error_logger.report_exception()
                # Because we're aggregating on the fly, sometimes the datetime
                # index can get messy until it's healed by the minute bars
                tlog(
                    f"[{self.name}] error aggregation {e} - maybe should use nearest?"
                )
                return False, {}

            back_time = ts(config.market_open)
            back_time_index = minute_history["close"].index.get_loc(
                back_time, method="nearest"
            )
            close = (
                minute_history["close"][back_time_index:]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .last()
            ).dropna()
            open = (
                minute_history["open"][back_time_index:]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .first()
            ).dropna()
            high = (
                minute_history["high"][back_time_index:]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .max()
            ).dropna()
            low = (
                minute_history["low"][back_time_index:]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .min()
            ).dropna()
            volume = (
                minute_history["volume"][back_time_index:]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .sum()
            ).dropna()

            _df = concat(
                [
                    open.rename("open"),
                    high.rename("close"),
                    low.rename("low"),
                    close.rename("close"),
                    volume.rename("volume"),
                ]
            )
            tlog(f"\n{tabulate(_df, headers='keys', tablefmt='psql')}")

            add_daily_vwap(_df)
            vwap_series = _df["average"]

            if (
                # data.vwap > close_series[-1] > close_series[-2]
                # and round(data.average, 2) > round(vwap_series[-1], 2)
                # and data.vwap > data.average
                # and
                data.low > data.average
                and close[-1] > vwap_series[-1] > vwap_series[-2] > close[-2]
                and prev_minute.high == prev_minute.close
            ):
                upperband, middleband, lowerband = BBANDS(
                    minute_history["close"], timeperiod=20,
                )

                stop_price = prev_minute.close
                target = upperband[-1]

                if target - stop_price < 0.05:
                    tlog(
                        f"target price {target} too close to stop price {stop_price}"
                    )
                    return False, {}

                stop_prices[symbol] = stop_price
                target_prices[symbol] = target

                patterns: Dict[ts, Dict[int, List[str]]] = {}
                pattern_functions = talib.get_function_groups()[
                    "Pattern Recognition"
                ]
                for pattern in pattern_functions:
                    pattern_value = getattr(talib, pattern)(
                        open, high, low, close
                    )
                    result = pattern_value.to_numpy().nonzero()
                    if result[0].size > 0:
                        for timestamp, value in pattern_value.iloc[
                            result
                        ].items():
                            t = ts(timestamp)
                            if t not in patterns:
                                patterns[t] = {}
                            if value not in patterns[t]:
                                patterns[t][value] = [pattern]
                            else:
                                patterns[t][value].append(pattern)

                tlog(f"{symbol} found conditions for VWAP strategy now:{now}")
                candle_s = Series(patterns)
                candle_s = candle_s.sort_index()
                tlog(f"{candle_s}")
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
                print(
                    f"shares to buy {shares_to_buy} {data.close} {stop_prices[symbol]}"
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
                        "average": round(data.average, 2),
                        "vwap": round(data.vwap, 2),
                        "patterns": candle_s.to_json(),
                    }

                    return (
                        True,
                        {
                            "side": "buy",
                            "qty": str(shares_to_buy),
                            "type": "limit",
                            "limit_price": str(prev_minute.close),
                        },
                    )
        elif (
            await super().is_sell_time(now)
            and position > 0
            and symbol in latest_cost_basis
            and last_used_strategy[symbol].name == self.name
        ):
            if data.vwap <= data.average:
                sell_indicators[symbol] = {
                    "reason": "below VWAP",
                    "average": data.average,
                    "vwap": data.vwap,
                }
                return (
                    True,
                    {"side": "sell", "qty": str(position), "type": "market",},
                )
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

        return False, {}
