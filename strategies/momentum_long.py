from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
import numpy as np
import talib
from google.cloud import error_reporting
from pandas import DataFrame as df
from pandas import Series
from pandas import Timestamp as ts
from talib import MACD, RSI

from common import config
from common.tlog import tlog
from common.trading_data import (buy_indicators, cool_down, latest_cost_basis,
                                 open_orders, sell_indicators, stop_prices,
                                 symbol_resistance, target_prices)
from fincalcs.candle_patterns import four_price_doji, gravestone_doji
from fincalcs.support_resistance import (find_resistances, find_stop,
                                         find_supports)

from .base import Strategy

error_logger = error_reporting.Client()


class MomentumLong(Strategy):
    name = "momentum_long"

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

    async def should_cool_down(self, symbol: str, now: datetime):
        if (
            symbol in cool_down
            and cool_down[symbol]
            and cool_down[symbol] >= now.replace(second=0, microsecond=0)
        ):
            return True

        cool_down[symbol] = None
        return False

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
        prev_min = minute_history.iloc[-2]
        if (
            await super().is_buy_time(now)
            and not position
            and not await self.should_cool_down(symbol, now)
        ):
            # Check for buy signals
            lbound = config.market_open
            ubound = lbound + timedelta(minutes=16)

            if debug:
                tlog(f"15 schedule {lbound}/{ubound}")
            try:
                high_15m = minute_history[lbound:ubound][  # type: ignore
                    "high"
                ].max()

                if debug:
                    tlog(f"{minute_history[lbound:ubound]}")
            except Exception as e:
                error_logger.report_exception()
                # Because we're aggregating on the fly, sometimes the datetime
                # index can get messy until it's healed by the minute bars
                tlog(
                    f"[{self.name}] error aggregation {e} - maybe should use nearest?"
                )
                return False, {}

            if debug:
                tlog(f"15 minutes high:{high_15m}")

            # Get the change since yesterday's market close
            if data.close > high_15m:  # and volume_today[symbol] > 30000:
                if debug:
                    tlog(
                        f"[{now}]{symbol} {data.close} above 15 minute high {high_15m}"
                    )

                # check for a positive, increasing MACD

                last_30_max_close = minute_history[-30:]["close"].max()
                last_30_min_close = minute_history[-30:]["close"].min()

                if (now - config.market_open).seconds // 60 > 40 and (
                    last_30_max_close - last_30_min_close
                ) / last_30_min_close > 0.1:
                    tlog(
                        f"[{self.name}] too sharp {symbol} increase in last 30 minutes, can't trust MACD, cool down for 15 minutes"
                    )
                    cool_down[symbol] = now.replace(
                        second=0, microsecond=0
                    ) + timedelta(minutes=15)
                    return False, {}

                serie = (
                    minute_history["close"]
                    .dropna()
                    .between_time("9:30", "16:00")
                )

                if data.vwap:
                    serie[-1] = data.vwap
                macds = MACD(serie)
                # await asyncio.sleep(0)

                sell_macds = MACD(serie, 13, 21)
                # await asyncio.sleep(0)
                macd1 = macds[0]
                macd_signal = macds[1]

                if debug:
                    if macd1[-1].round(2) > 0:
                        tlog(f"[{now}]{symbol} MACD > 0")
                    if (
                        macd1[-3].round(3)
                        < macd1[-2].round(3)
                        < macd1[-1].round(3)
                    ):
                        tlog(f"[{now}]{symbol} MACD trending")
                    else:
                        tlog(f"[{now}]{symbol} MACD NOT trending -> failed")
                    if macd1[-1] > macd_signal[-1]:
                        tlog(f"[{now}]{symbol} MACD above signal")
                    else:
                        tlog(f"[{now}]{symbol} MACD BELOW signal -> failed")
                    if data.close >= data.open:
                        tlog(f"[{now}]{symbol} above open")
                    else:
                        tlog(
                            f"[{now}]{symbol} close {data.close} BELOW open {data.open} -> failed"
                        )
                if (
                    macd1[-1].round(2) > 0
                    and macd1[-3].round(3)
                    < macd1[-2].round(3)
                    < macd1[-1].round(3)
                    and macd1[-1] > macd_signal[-1]
                    and sell_macds[0][-1] > 0
                    and data.vwap > data.open
                    # and 0 < macd1[-2] - macd1[-3] < macd1[-1] - macd1[-2]
                ):
                    tlog(
                        f"[{self.name}] MACD(12,26) for {symbol} trending up!, MACD(13,21) trending up and above signals"
                    )
                    macd2 = MACD(serie, 40, 60)[0]
                    # await asyncio.sleep(0)
                    if macd2[-1] >= 0 and np.diff(macd2)[-1] >= 0:
                        tlog(
                            f"[{self.name}] MACD(40,60) for {symbol} trending up!"
                        )
                        # check RSI does not indicate overbought
                        rsi = RSI(serie, 14)
                        # await asyncio.sleep(0)
                        tlog(f"[{self.name}] {symbol} RSI={round(rsi[-1], 2)}")
                        if rsi[-1] <= 71:
                            tlog(
                                f"[{self.name}] {symbol} RSI {round(rsi[-1], 2)} <= 71"
                            )

                            resistance = await find_resistances(
                                symbol,
                                self.name,
                                min(
                                    data.low, prev_min.close
                                ),  # data.close if not data.vwap else data.vwap,
                                minute_history,
                                debug,
                            )

                            supports = await find_supports(
                                symbol,
                                self.name,
                                min(
                                    data.low, prev_min.close
                                ),  # data.close if not data.vwap else data.vwap,
                                minute_history,
                                debug,
                            )
                            if resistance is None or resistance == []:
                                tlog(
                                    f"[{self.name}] no resistance for {symbol} -> skip buy"
                                )
                                cool_down[symbol] = now.replace(
                                    second=0, microsecond=0
                                )
                                return False, {}

                            next_resistance = None
                            for potential_resistance in resistance:
                                if potential_resistance > data.close:
                                    next_resistance = potential_resistance
                                    break

                            if not next_resistance:
                                tlog(
                                    f"[{self.name}] did not find resistance above {data.close}"
                                )
                                return False, {}

                            if next_resistance - data.close < 0.05:
                                tlog(
                                    f"[{self.name}] {symbol} at price {data.close} too close to resistance {next_resistance}"
                                )
                                return False, {}
                            if data.close - supports[-1] < 0.05:
                                tlog(
                                    f"[{self.name}] {symbol} at price {data.close} too close to support {supports[-1]} -> trend not established yet"
                                )
                                return False, {}
                            if (next_resistance - data.close) / (
                                data.close - supports[-1]
                            ) < 0.8:
                                tlog(
                                    f"[{self.name}] {symbol} at price {data.close} missed entry point between support {supports[-1]} and resistance {next_resistance}"
                                )
                                cool_down[symbol] = now.replace(
                                    second=0, microsecond=0
                                )
                                return False, {}

                            tlog(
                                f"[{self.name}] {symbol} at price {data.close} found entry point between support {supports[-1]} and resistance {next_resistance}"
                            )
                            # Stock has passed all checks; figure out how much to buy
                            stop_price = find_stop(
                                data.close if not data.vwap else data.vwap,
                                minute_history,
                                now,
                            )
                            stop_prices[symbol] = min(
                                stop_price, supports[-1] - 0.05
                            )
                            target_prices[symbol] = (
                                data.close
                                + (data.close - stop_prices[symbol]) * 2
                            )
                            symbol_resistance[symbol] = next_resistance

                            if portfolio_value is None:
                                if trading_api:
                                    portfolio_value = float(
                                        trading_api.get_account().portfolio_value
                                    )
                                else:
                                    raise Exception(
                                        "MomentumLong.run(): both portfolio_value and trading_api can't be None"
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
                                    f"[{self.name}] Submitting buy for {shares_to_buy} shares of {symbol} at {data.close} target {target_prices[symbol]} stop {stop_price}"
                                )

                                # await asyncio.sleep(0)
                                buy_indicators[symbol] = {
                                    "rsi": rsi[-1].tolist(),
                                    "macd": macd1[-5:].tolist(),
                                    "macd_signal": macd_signal[-5:].tolist(),
                                    "slow macd": macd2[-5:].tolist(),
                                    "sell_macd": sell_macds[0][-5:].tolist(),
                                    "sell_macd_signal": sell_macds[1][
                                        -5:
                                    ].tolist(),
                                    "resistances": resistance,
                                    "supports": supports,
                                    "vwap": data.vwap,
                                    "avg": data.average,
                                    "position_ratio": str(
                                        round(
                                            (next_resistance - data.close)
                                            / (data.close - supports[-1]),
                                            2,
                                        )
                                    ),
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

                    else:
                        tlog(f"[{self.name}] failed MACD(40,60) for {symbol}!")

        if (
            await super().is_sell_time(now)
            and position > 0
            and symbol in latest_cost_basis
        ):
            if open_orders.get(symbol) is not None:
                tlog(
                    f"momentum_long: open order for {symbol} exists, skipping"
                )
                return False, {}

            # Check for liquidation signals
            # Sell for a loss if it's fallen below our stop price
            # Sell for a loss if it's below our cost basis and MACD < 0
            # Sell for a profit if it's above our target price
            macds = MACD(
                minute_history["close"].dropna().between_time("9:30", "16:00"),
                13,
                21,
            )
            # await asyncio.sleep(0)
            macd = macds[0]
            macd_signal = macds[1]
            rsi = RSI(
                minute_history["close"].dropna().between_time("9:30", "16:00"),
                14,
            )
            movement = (
                data.close - latest_cost_basis[symbol]
            ) / latest_cost_basis[symbol]
            macd_val = macd[-1]
            macd_signal_val = macd_signal[-1]

            round_factor = (
                2 if macd_val >= 0.1 or macd_signal_val >= 0.1 else 3
            )
            # await asyncio.sleep(0)
            if (
                symbol_resistance
                and symbol in symbol_resistance
                and symbol_resistance[symbol]
            ):
                scalp_threshold = (
                    symbol_resistance[symbol] + latest_cost_basis[symbol]
                ) / 2.0
            else:
                scalp_threshold = (
                    target_prices[symbol] + latest_cost_basis[symbol]
                ) / 2.0
            bail_threshold = (
                latest_cost_basis[symbol] + scalp_threshold
            ) / 2.0
            macd_below_signal = round(macd_val, round_factor) < round(
                macd_signal_val, round_factor
            )
            bail_out = (
                # movement > min(0.02, movement_threshold) and macd_below_signal
                data.vwap > bail_threshold
                and macd_below_signal
                and macd[-1] < macd[-2]
            )
            bail_on_rsi = data.vwap > bail_threshold and rsi[-2] < rsi[-3]

            if debug and not bail_out:
                tlog(
                    f"[{now}]{symbol} don't bail: data.vwap={data.vwap} bail_threshold={bail_threshold} macd_below_signal={macd_below_signal} macd[-1]={ macd[-1]} macd[-2]={macd[-2]}"
                )

            scalp = movement > 0.02 or data.vwap > scalp_threshold
            below_cost_base = data.vwap < latest_cost_basis[symbol]

            to_sell = False
            partial_sell = False
            sell_reasons = []
            if data.close <= stop_prices[symbol]:
                to_sell = True
                sell_reasons.append("stopped")
            elif (
                below_cost_base
                and round(macd_val, 2) < 0
                and rsi[-1] < rsi[-2]
                and round(macd[-1], 2) < round(macd[-2], 2)
            ):
                to_sell = True
                sell_reasons.append(
                    "below cost & macd negative & RSI trending down"
                )
            elif data.close >= target_prices[symbol] and macd[-1] <= 0:
                to_sell = True
                sell_reasons.append("above target & macd negative")
            elif rsi[-1] >= 79:
                to_sell = True
                sell_reasons.append("rsi max, cool-down for 5 minutes")
                cool_down[symbol] = now.replace(
                    second=0, microsecond=0
                ) + timedelta(minutes=5)
            elif bail_out:
                to_sell = True
                sell_reasons.append("bail")
            elif bail_on_rsi:
                to_sell = True
                sell_reasons.append("bail_on_rsi")
            elif scalp:
                partial_sell = True
                to_sell = True
                sell_reasons.append("scale-out")
            elif gravestone_doji(data.open, data.close, data.high, data.low):
                if debug:
                    tlog(
                        f"identified gravestone doji {data.open, data.close, data.low, data.high}"
                    )
                prev_data = minute_history.iloc[-2]
                if prev_data.close > prev_data.open:
                    if debug:
                        tlog(f"identified up-trend before gravestone doji")

                    if rsi[-1] >= 70:
                        if debug:
                            tlog(f"RSI >= 70, accept doji")
                        to_sell = True
                        sell_reasons.append("gravestone doji")
                        if debug:
                            tlog("sell on gravestone doji")
                    elif debug:
                        tlog(f"RSI < 70, do NOT accept doji")

                elif debug:
                    tlog("gravestone doji did not follow up trend")

            if to_sell:
                # await asyncio.sleep(0)
                try:
                    close = minute_history["close"][-10:].dropna()
                    open = minute_history["open"][-10:].dropna()
                    high = minute_history["high"][-10:].dropna()
                    low = minute_history["low"][-10:].dropna()

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
                    candle_s = Series(patterns)
                    candle_s = candle_s.sort_index()

                    sell_indicators[symbol] = {
                        "rsi": rsi[-3:].tolist(),
                        "movement": movement,
                        "sell_macd": macd[-5:].tolist(),
                        "sell_macd_signal": macd_signal[-5:].tolist(),
                        "vwap": data.vwap,
                        "avg": data.average,
                        "reasons": " AND ".join(
                            [str(elem) for elem in sell_reasons]
                        ),
                        "patterns": candle_s.to_json()
                        if candle_s.size > 0
                        else None,
                    }

                    if not partial_sell:
                        tlog(
                            f"[{self.name}] Submitting sell for {position} shares of {symbol} at market"
                        )
                        return (
                            True,
                            {
                                "side": "sell",
                                "qty": str(position),
                                "type": "market",
                            },
                        )
                    else:
                        qty = int(position / 2) if position > 1 else 1
                        tlog(
                            f"[{self.name}] Submitting sell for {str(qty)} shares of {symbol} at limit of {data.close}"
                        )
                        return (
                            True,
                            {
                                "side": "sell",
                                "qty": str(qty),
                                "type": "limit",
                                "limit_price": str(data.close),
                            },
                        )

                except Exception:
                    error_logger.report_exception()

        return False, {}
