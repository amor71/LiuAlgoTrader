import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df
from stockstats import StockDataFrame

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.tlog import tlog
from liualgotrader.common.trading_data import (buy_indicators, buy_time,
                                               cool_down, last_used_strategy,
                                               latest_cost_basis,
                                               latest_scalp_basis, open_orders,
                                               sell_indicators, stop_prices,
                                               target_prices)
from liualgotrader.fincalcs.support_resistance import find_stop
from liualgotrader.strategies.base import Strategy, StrategyType


class MomentumLongV3(Strategy):
    name = "momentum_long"
    whipsawed: Dict = {}

    def __init__(
        self,
        batch_id: str,
        schedule: List[Dict],
        ref_run_id: int = None,
        check_patterns: bool = False,
        data_loader: DataLoader = None,
    ):
        self.check_patterns = check_patterns
        super().__init__(
            name=type(self).__name__,
            type=StrategyType.DAY_TRADE,
            batch_id=batch_id,
            ref_run_id=ref_run_id,
            data_loader=data_loader,
            schedule=schedule,
        )

    async def buy_callback(
        self,
        symbol: str,
        price: float,
        qty: float,
        now: datetime = None,
        trade_fee: float = 0.0,
    ) -> None:
        """Called by Framework, upon successful buy (could be partial)"""
        latest_scalp_basis[symbol] = latest_cost_basis[symbol] = price

    async def sell_callback(
        self,
        symbol: str,
        price: float,
        qty: float,
        now: datetime = None,
        trade_fee: float = 0.0,
    ) -> None:
        latest_scalp_basis[symbol] = price

    async def create(self) -> bool:
        await super().create()
        tlog(f"strategy {self.name} created")
        return True

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
        shortable: bool,
        position: float,
        now: datetime,
        minute_history: df,
        portfolio_value: float = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        data = minute_history.iloc[-1]
        prev_min = minute_history.iloc[-2]

        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        morning_rush = (now - market_open).seconds // 60 < 30

        if (
            await super().is_buy_time(now)
            and not position
            and not open_orders.get(symbol, None)
            and not await self.should_cool_down(symbol, now)
        ):
            # Check for buy signals
            lbound = market_open
            ubound = lbound + timedelta(minutes=15)
            try:
                high_15m = minute_history[lbound:ubound]["high"].max()  # type: ignore
            except Exception as e:

                tlog(
                    f"{symbol}[{now}] failed to aggregate {lbound}:{ubound} {minute_history}"
                )
                return False, {}

            if data.close > high_15m:
                close = (
                    minute_history["close"]
                    .dropna()
                    .between_time("9:30", "16:00")
                )

                old_stdout = sys.stdout  # backup current stdout
                sys.stdout = open(os.devnull, "w")

                stock = StockDataFrame(close)

                macd = stock["macd"]
                macd_signal = stock["macds"]
                macd_hist = stock["macdh"]

                sys.stdout = old_stdout  # reset old stdout

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
                    and (
                        data.vwap > data.open > prev_min.close
                        and data.vwap != 0.0
                        or data.vwap == 0.0
                        and data.close > data.open > prev_min.close
                    )
                ):

                    if debug:
                        tlog(f"[{self.name}][{now}] slow macd confirmed trend")

                    # check RSI does not indicate overbought
                    rsi = stock["rsi_20"]

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
                    target_price = 3 * (data.close - stop_price) + data.close
                    target_prices[symbol] = target_price
                    stop_prices[symbol] = stop_price

                    shares_to_buy = (
                        portfolio_value  # type: ignore
                        * config.risk
                        // (data.close - stop_prices[symbol])
                    )
                    if not shares_to_buy:
                        shares_to_buy = 1
                    shares_to_buy -= position
                    if shares_to_buy > 0:
                        self.whipsawed[symbol] = False

                        buy_price = max(data.close, data.vwap)
                        tlog(
                            f"[{self.name}][{now}] Submitting buy for {shares_to_buy} shares of {symbol} at {buy_price} target {target_prices[symbol]} stop {stop_prices[symbol]}"
                        )

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
            elif debug:
                tlog(f"[{self.name}][{now}] {data.close} < 15min high ")
        if (
            await super().is_sell_time(now)
            and position > 0
            and symbol in latest_cost_basis
            and last_used_strategy[symbol].name == self.name
            and not open_orders.get(symbol)
        ):
            if (
                not self.whipsawed.get(symbol, None)
                and data.close < latest_cost_basis[symbol] * 0.99
            ):
                self.whipsawed[symbol] = True

            serie = (
                minute_history["close"].dropna().between_time("9:30", "16:00")
            )

            if data.vwap:
                serie[-1] = data.vwap

            old_stdout = sys.stdout  # backup current stdout
            sys.stdout = open(os.devnull, "w")

            stock = StockDataFrame(serie)
            stock.MACD_EMA_SHORT = 13
            stock.MACD_EMA_LONG = 21

            macd = stock["macd"]
            macd_signal = stock["macds"]

            rsi = stock["rsi_20"]

            sys.stdout = old_stdout  # reset old stdout

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
                (
                    latest_scalp_basis[symbol] > latest_cost_basis[symbol]
                    or movement > 0.02
                )
                and macd_below_signal
                and round(macd[-1], round_factor)
                < round(macd[-2], round_factor)
            )
            bail_on_whipsawed = (
                self.whipsawed.get(symbol, False)
                and data.close > latest_cost_basis[symbol]
                and macd_below_signal
                and round(macd[-1], round_factor)
                < round(macd[-2], round_factor)
            )
            scalp = movement > 0.04 or data.vwap > scalp_threshold
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
            elif bail_on_whipsawed:
                to_sell = True
                partial_sell = False
                limit_sell = True
                sell_reasons.append("bail post whipsawed")

            if to_sell:
                sell_indicators[symbol] = {
                    "rsi": rsi[-3:].tolist(),
                    "movement": movement,
                    "sell_macd": macd[-5:].tolist(),
                    "sell_macd_signal": macd_signal[-5:].tolist(),
                    "vwap": data.vwap,
                    "avg": data.average,
                    "reasons": " AND ".join(
                        str(elem) for elem in sell_reasons
                    ),
                }

                if partial_sell:
                    qty = int(position / 2) if position > 1 else 1
                    tlog(
                        f'[{self.name}][{now}] Submitting sell for {qty} shares of {symbol} at limit of {data.close}with reason:{sell_reasons}'
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

                else:
                    if limit_sell:
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
        return False, {}
