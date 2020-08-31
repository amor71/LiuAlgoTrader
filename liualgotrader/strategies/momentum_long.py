from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
import numpy as np
import talib
from pandas import DataFrame as df
from talib import BBANDS, MACD, RSI

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.trading_data import (buy_indicators, buy_time,
                                               cool_down, last_used_strategy,
                                               latest_cost_basis,
                                               latest_scalp_basis, open_orders,
                                               sell_indicators, stop_prices,
                                               target_prices)
from liualgotrader.fincalcs.support_resistance import find_stop
from liualgotrader.strategies.base import Strategy, StrategyType


class MomentumLong(Strategy):
    name = "momentum_long"

    def __init__(
        self,
        batch_id: str,
        schedule: List[Dict],
        ref_run_id: int = None,
        check_patterns: bool = False,
    ):
        self.check_patterns = check_patterns
        super().__init__(
            name=self.name,
            type=StrategyType.DAY_TRADE,
            batch_id=batch_id,
            ref_run_id=ref_run_id,
            schedule=schedule,
        )

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_scalp_basis[symbol] = latest_cost_basis[symbol] = price

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_scalp_basis[symbol] = price

    async def create(self) -> None:
        await super().create()
        tlog(f"strategy {self.name} created")

    async def should_cool_down(self, symbol: str, now: datetime):
        if (
            symbol in cool_down
            and cool_down[symbol]
            and cool_down[symbol] >= now.replace(second=0, microsecond=0)  # type: ignore
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

        morning_rush = (
            True if (now - config.market_open).seconds // 60 < 30 else False
        )

        if (
            await super().is_buy_time(now)
            and not position
            and not await self.should_cool_down(symbol, now)
        ):
            # Check for buy signals
            lbound = config.market_open
            ubound = lbound + timedelta(minutes=15)

            if debug:
                tlog(f"15 schedule {lbound}/{ubound}")
            try:
                high_15m = minute_history[lbound:ubound][  # type: ignore
                    "high"
                ].max()
            except Exception as e:
                tlog(
                    f"[{self.name}] error aggregation {e} - maybe should use nearest?"
                )
                return False, {}

            if data.close > high_15m or (
                hasattr(config, "bypass_market_schedule")
                and config.bypass_market_schedule
            ):
                close = (
                    minute_history["close"]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                close_5m = (
                    minute_history["close"]
                    .dropna()
                    .between_time("9:30", "16:00")
                    .resample("5min")
                    .last()
                ).dropna()

                macds = MACD(close)
                # sell_macds = MACD(close, 13, 21)

                macd = macds[0]
                macd_signal = macds[1]
                macd_hist = macds[2]
                macd_trending = macd[-3] < macd[-2] < macd[-1]
                macd_above_signal = macd[-1] > macd_signal[-1] * 1.1
                macd_hist_trending = (
                    macd_hist[-3] < macd_hist[-2] < macd_hist[-1]
                )

                if (
                    macd[-1] > 0
                    and macd_trending
                    and macd_above_signal
                    and macd_hist_trending
                ):
                    macd2 = MACD(close, 40, 60)[0]
                    if macd2[-1] >= 0 and np.diff(macd2)[-1] >= 0:
                        if debug:
                            tlog(
                                f"[{self.name}][{now}] slow macd confirmed trend"
                            )

                        # check RSI does not indicate overbought
                        rsi = RSI(close, 14)

                        if debug:
                            tlog(
                                f"[{self.name}][{now}] {symbol} RSI={round(rsi[-1], 2)}"
                            )

                        rsi_limit = 75
                        if rsi[-1] < rsi_limit:
                            if debug:
                                tlog(
                                    f"[{self.name}][{now}] {symbol} RSI {round(rsi[-1], 2)} <= {rsi_limit}"
                                )
                        else:
                            tlog(
                                f"[{self.name}][{now}] {symbol} RSI over-bought, cool down for 5 min"
                            )
                            cool_down[symbol] = now.replace(
                                second=0, microsecond=0
                            ) + timedelta(minutes=5)

                            return False, {}

                        stop_price = find_stop(
                            data.close if not data.vwap else data.vwap,
                            minute_history,
                            now,
                        )
                        target_price = (
                            3 * (data.close - stop_price) + data.close
                        )
                        target_prices[symbol] = target_price
                        stop_prices[symbol] = stop_price

                        if portfolio_value is None:
                            if trading_api:
                                portfolio_value = float(
                                    trading_api.get_account().portfolio_value
                                )
                            else:
                                raise Exception(
                                    f"{self.name}: both portfolio_value and trading_api can't be None"
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
                            buy_price = max(data.close, data.vwap)
                            tlog(
                                f"[{self.name}][{now}] Submitting buy for {shares_to_buy} shares of {symbol} at {buy_price} target {target_prices[symbol]} stop {stop_prices[symbol]}"
                            )

                            # await asyncio.sleep(0)
                            buy_indicators[symbol] = {
                                "macd": macd[-5:].tolist(),
                                "macd_signal": macd_signal[-5:].tolist(),
                                "vwap": data.vwap,
                                "avg": data.average,
                            }

                            return (
                                True,
                                {
                                    "side": "buy",
                                    "qty": str(shares_to_buy),
                                    "type": "limit",
                                    "limit_price": str(buy_price),
                                }
                                if not morning_rush
                                else {
                                    "side": "buy",
                                    "qty": str(shares_to_buy),
                                    "type": "market",
                                },
                            )
            else:
                if debug:
                    tlog(f"[{self.name}][{now}] {data.close} < 15min high ")
        if (
            await super().is_sell_time(now)
            and position > 0
            and symbol in latest_cost_basis
            and last_used_strategy[symbol].name == self.name
        ):
            if open_orders.get(symbol) is not None:
                tlog(
                    f"momentum_long: open order for {symbol} exists, skipping"
                )
                return False, {}

            macds = MACD(
                minute_history["close"].dropna().between_time("9:30", "16:00"),
                13,
                21,
            )
            macd = macds[0]
            macd_signal = macds[1]
            rsi = RSI(
                minute_history["close"].dropna().between_time("9:30", "16:00"),
                14,
            )

            movement = (
                data.close - latest_scalp_basis[symbol]
            ) / latest_scalp_basis[symbol]
            macd_val = macd[-1]
            macd_signal_val = macd_signal[-1]

            round_factor = (
                2 if macd_val >= 0.1 or macd_signal_val >= 0.1 else 3
            )
            scalp_threshold = (
                target_prices[symbol] + latest_scalp_basis[symbol]
            ) / 2.0

            macd_below_signal = round(macd_val, round_factor) < round(
                macd_signal_val, round_factor
            )
            bail_out = (
                latest_scalp_basis[symbol] > latest_cost_basis[symbol]
                and macd_below_signal
                and round(macd[-1], round_factor)
                < round(macd[-2], round_factor)
            )

            scalp = movement > 0.02 or data.vwap > scalp_threshold
            below_cost_base = data.vwap < latest_cost_basis[symbol]

            rsi_limit = 79 if not morning_rush else 85
            to_sell = False
            partial_sell = False
            limit_sell = False
            sell_reasons = []
            if data.close <= stop_prices[symbol]:
                to_sell = True
                sell_reasons.append("stopped")
            elif (
                below_cost_base
                and round(macd_val, 2) < 0
                and rsi[-1] < rsi[-2]
                and round(macd[-1], round_factor)
                < round(macd[-2], round_factor)
                and data.vwap < 0.95 * data.average
            ):
                to_sell = True
                sell_reasons.append(
                    "below cost & macd negative & RSI trending down and too far from VWAP"
                )
            elif data.close >= target_prices[symbol] and macd[-1] <= 0:
                to_sell = True
                sell_reasons.append("above target & macd negative")
            elif rsi[-1] >= rsi_limit:
                to_sell = True
                sell_reasons.append("rsi max, cool-down for 5 minutes")
                cool_down[symbol] = now.replace(
                    second=0, microsecond=0
                ) + timedelta(minutes=5)
            elif bail_out:
                to_sell = True
                sell_reasons.append("bail")
            elif scalp:
                partial_sell = True
                to_sell = True
                sell_reasons.append("scale-out")

            if to_sell:
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
                }

                if not partial_sell:
                    if not limit_sell:
                        tlog(
                            f"[{self.name}][{now}] Submitting sell for {position} shares of {symbol} at market with reason:{sell_reasons}"
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
                        tlog(
                            f"[{self.name}][{now}] Submitting sell for {position} shares of {symbol} at {data.close} with reason:{sell_reasons}"
                        )
                        return (
                            True,
                            {
                                "side": "sell",
                                "qty": str(position),
                                "type": "limit",
                                "limit_price": str(data.close),
                            },
                        )
                else:
                    qty = int(position / 2) if position > 1 else 1
                    tlog(
                        f"[{self.name}][{now}] Submitting sell for {str(qty)} shares of {symbol} at limit of {data.close }with reason:{sell_reasons}"
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

        return False, {}
