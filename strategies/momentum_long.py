import asyncio
from datetime import datetime, timedelta

import alpaca_trade_api as tradeapi
import numpy as np
from google.cloud import error_reporting
from pandas import DataFrame as df
from talib import MACD, RSI

from common import config
from common.market_data import volume_today
from common.tlog import tlog
from common.trading_data import (buy_indicators, cool_down, latest_cost_basis,
                                 open_order_strategy, open_orders,
                                 sell_indicators, stop_prices,
                                 symbol_resistance, target_prices)
from fincalcs.support_resistance import (find_resistances, find_stop,
                                         find_supports)

from .base import Strategy

error_logger = error_reporting.Client()


class MomentumLong(Strategy):
    name = "momentum_long"

    def __init__(self, trading_api: tradeapi, batch_id: str):
        super().__init__(
            name=self.name, trading_api=trading_api, batch_id=batch_id
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
        self, symbol: str, position: int, minute_history: df, now: datetime
    ) -> bool:
        data = minute_history.iloc[-1]
        if (
            await super().is_buy_time(now)
            and not position
            and not await self.should_cool_down(symbol, now)
        ):
            # Check for buy signals
            lbound = config.market_open
            ubound = lbound + timedelta(minutes=15)
            try:
                high_15m = minute_history[lbound:ubound][  # type: ignore
                    "high"
                ].max()
            except Exception as e:
                error_logger.report_exception()
                # Because we're aggregating on the fly, sometimes the datetime
                # index can get messy until it's healed by the minute bars
                tlog(
                    f"[{self.name}] error aggregation {e} - maybe should use nearest?"
                )
                return False

            # Get the change since yesterday's market close
            if data.close > high_15m and volume_today[symbol] > 30000:
                # check for a positive, increasing MACD
                macds = MACD(
                    minute_history["close"]
                    .dropna()
                    .between_time("9:30", "16:00")
                )
                # await asyncio.sleep(0)
                sell_macds = MACD(
                    minute_history["close"]
                    .dropna()
                    .between_time("9:30", "16:00"),
                    13,
                    21,
                )
                # await asyncio.sleep(0)
                macd1 = macds[0]
                macd_signal = macds[1]
                if (
                    macd1[-1].round(2) > 0
                    and macd1[-3].round(3)
                    < macd1[-2].round(3)
                    < macd1[-1].round(3)
                    and macd1[-1] > macd_signal[-1]
                    and sell_macds[0][-1] > 0
                    and data.close > data.open
                    # and 0 < macd1[-2] - macd1[-3] < macd1[-1] - macd1[-2]
                ):
                    tlog(
                        f"[{self.name}] MACD(12,26) for {symbol} trending up!, MACD(13,21) trending up and above signals"
                    )
                    macd2 = MACD(
                        minute_history["close"]
                        .dropna()
                        .between_time("9:30", "16:00"),
                        40,
                        60,
                    )[0]
                    # await asyncio.sleep(0)
                    if macd2[-1] >= 0 and np.diff(macd2)[-1] >= 0:
                        tlog(
                            f"[{self.name}] MACD(40,60) for {symbol} trending up!"
                        )
                        # check RSI does not indicate overbought
                        rsi = RSI(
                            minute_history["close"]
                            .dropna()
                            .between_time("9:30", "16:00"),
                            14,
                        )
                        # await asyncio.sleep(0)
                        tlog(f"[{self.name}] RSI={round(rsi[-1], 2)}")
                        if rsi[-1] <= 70:
                            tlog(
                                f"[{self.name}] {symbol} RSI {round(rsi[-1], 2)} <= 70"
                            )
                            resistance = await find_resistances(
                                symbol, self.name, data.close, minute_history
                            )
                            supports = await find_supports(
                                symbol, self.name, data.close, minute_history
                            )
                            if resistance is None or resistance == []:
                                tlog(
                                    f"[{self.name}]no resistance for {symbol} -> skip buy"
                                )
                                cool_down[symbol] = now.replace(
                                    second=0, microsecond=0
                                )
                                return False

                            if (resistance[0] - data.close) / (
                                data.close - supports[-1]
                            ) < 0.8:
                                tlog(
                                    f"[{self.name}] {symbol} at price {data.close} missed entry point between support {supports[-1]} and resistance {resistance[0]}"
                                )
                                cool_down[symbol] = now.replace(
                                    second=0, microsecond=0
                                )
                                return False

                            tlog(
                                f"[{self.name}] {symbol} at price {data.close} found entry point between support {supports[-1]} and resistance {resistance[0]}"
                            )
                            # Stock has passed all checks; figure out how much to buy
                            stop_price = find_stop(
                                data.close, minute_history, now
                            )
                            stop_prices[symbol] = min(
                                stop_price, supports[-1] - 0.05
                            )
                            target_prices[symbol] = (
                                data.close
                                + (data.close - stop_prices[symbol]) * 2
                            )
                            symbol_resistance[symbol] = resistance[0]
                            portfolio_value = float(
                                self.trading_api.get_account().portfolio_value
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

                                try:
                                    # await asyncio.sleep(0)
                                    buy_indicators[symbol] = {
                                        "rsi": rsi[-1].tolist(),
                                        "macd": macd1[-5:].tolist(),
                                        "macd_signal": macd_signal[
                                            -5:
                                        ].tolist(),
                                        "slow macd": macd2[-5:].tolist(),
                                        "sell_macd": sell_macds[0][
                                            -5:
                                        ].tolist(),
                                        "sell_macd_signal": sell_macds[1][
                                            -5:
                                        ].tolist(),
                                        "resistances": resistance,
                                        "supports": supports,
                                        "vwap": data.vwap,
                                        "avg": data.average,
                                        "position_ratio": str(
                                            round(
                                                (resistance[0] - data.close)
                                                / (data.close - supports[-1]),
                                                2,
                                            )
                                        ),
                                    }
                                    o = self.trading_api.submit_order(
                                        symbol=symbol,
                                        qty=str(shares_to_buy),
                                        side="buy",
                                        type="limit",
                                        time_in_force="day",
                                        limit_price=str(data.close),
                                    )
                                    open_orders[symbol] = (o, "buy")
                                    open_order_strategy[symbol] = self
                                    return True

                                except Exception:
                                    error_logger.report_exception()
                    else:
                        tlog(f"[{self.name}] failed MACD(40,60) for {symbol}!")
            elif volume_today[symbol] < 30000:
                tlog(f"volume for {symbol} too low")

        if (
            await super().is_sell_time(now)
            and position > 0
            and symbol in latest_cost_basis
        ):
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
            # await asyncio.sleep(0)
            scalp_threshold = (
                symbol_resistance[symbol] + latest_cost_basis[symbol]
            ) / 2.0
            bail_threshold = (
                latest_cost_basis[symbol] + scalp_threshold
            ) / 2.0
            macd_below_signal = macd_val < macd_signal_val
            bail_out = (
                # movement > min(0.02, movement_threshold) and macd_below_signal
                data.close > bail_threshold
                and macd_below_signal
                and macd[-1] < macd[-2]
            )
            scalp = movement > 0.02 or data.close > scalp_threshold
            # below_cost_base = data.close <= latest_cost_basis[symbol]

            to_sell = False
            partial_sell = False
            sell_reasons = []
            if data.close <= stop_prices[symbol]:
                to_sell = True
                sell_reasons.append("stopped")
            #           elif below_cost_base and macd_val <= 0 and rsi[-1] < rsi[-2]:
            #               to_sell = True
            #               sell_reasons.append(
            #                   "below cost & macd negative & RSI trending down"
            #               )
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
            elif scalp:
                partial_sell = True
                to_sell = True
                sell_reasons.append("scale-out")

            if to_sell:
                # await asyncio.sleep(0)
                try:
                    sell_indicators[symbol] = {
                        "rsi": rsi[-2:].tolist(),
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
                        tlog(
                            f"[{self.name}] Submitting sell for {position} shares of {symbol} at market"
                        )
                        o = self.trading_api.submit_order(
                            symbol=symbol,
                            qty=str(position),
                            side="sell",
                            type="market",
                            time_in_force="day",
                        )
                    else:
                        qty = int(position / 2) if position > 1 else 1
                        tlog(
                            f"[{self.name}] Submitting sell for {str(qty)} shares of {symbol} at limit of {data.close}"
                        )
                        o = self.trading_api.submit_order(
                            symbol=symbol,
                            qty=str(qty),
                            side="sell",
                            type="limit",
                            time_in_force="day",
                            limit_price=str(data.close),
                        )

                    open_orders[symbol] = (o, "sell")
                    open_order_strategy[symbol] = self
                    return True
                except Exception:
                    error_logger.report_exception()

        return False
