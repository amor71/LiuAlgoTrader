import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df
from talib import MAMA

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.trading_data import (
    buy_indicators,
    last_used_strategy,
    latest_cost_basis,
    open_orders,
    sell_indicators,
    stop_prices,
    target_prices,
)
from liualgotrader.strategies.base import Strategy, StrategyType


class SwingMamaFama(Strategy):
    name = "SwingMamaFama"
    was_above_vwap: Dict = {}

    def __init__(
        self,
        batch_id: str,
        ref_run_id: int = None,
    ):
        super().__init__(
            name=self.name,
            type=StrategyType.SWING,
            batch_id=batch_id,
            ref_run_id=ref_run_id,
            schedule=[],
        )

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_cost_basis[symbol] = price

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        pass

    async def create(self) -> None:
        await super().create()
        tlog(f"strategy {self.name} created")

    async def is_buy_time(self, now: datetime):
        return True

    async def is_sell_time(self, now: datetime):
        return True

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
        data = minute_history.iloc[-1]
        mama, fama = MAMA(minute_history["close"])

        if mama[-1] > fama[-1]:
            buy_price = data.close
            stop_price = data.close * 0.98
            target_price = data.close * 1.05

            stop_prices[symbol] = stop_price
            target_prices[symbol] = target_price

            if portfolio_value is None:
                if not trading_api:
                    raise Exception(
                        f"{self.name}: both portfolio_value and trading_api can't be None"
                    )

                retry = 3
                while retry > 0:
                    try:
                        portfolio_value = float(
                            trading_api.get_account().portfolio_value
                        )
                        break
                    except ConnectionError as e:
                        tlog(
                            f"[{symbol}][{now}[Error] get_account() failed w/ {e}, retrying {retry} more times"
                        )
                        await asyncio.sleep(0)
                        retry -= 1

                if not portfolio_value:
                    tlog("f[{symbol}][{now}[Error] failed to get portfolio_value")
                    return False, {}
            shares_to_buy = (
                portfolio_value * config.risk // (data.close - stop_prices[symbol])
            )
            if not shares_to_buy:
                shares_to_buy = 1

            buy_indicators[symbol] = {
                "mama": mama[-5:].tolist(),
                "fama": fama[-5:].tolist(),
            }

            tlog(
                f"[{self.name}][{now}] Submitting buy for {shares_to_buy} shares of {symbol} at {buy_price} target {target_prices[symbol]} stop {stop_prices[symbol]}"
            )

            return True, {
                "side": "buy",
                "qty": str(shares_to_buy),
                "type": "limit",
                "limit_price": str(buy_price),
            }

        if (
            await self.is_sell_time(now)
            and position
            and last_used_strategy[symbol].name == self.name
            and not open_orders.get(symbol)
        ):
            mama, fama = MAMA(minute_history["close"])

            to_sell: bool = False
            if data.close < stop_prices[symbol]:
                reason = "stopped"
                to_sell = True
            elif data.close >= target_prices[symbol]:
                reason = "target reached"
                to_sell = True
            elif mama[-1] < fama[-1]:
                reason = "fama below mama"
                to_sell = True

            if to_sell:
                tlog(
                    f"[{self.name}][{now}] Submitting sell for {position} shares of {symbol} at market {data.close} w reason {reason}"
                )

                sell_indicators[symbol] = {
                    "mama": mama[-5:].tolist(),
                    "fama": fama[-5:].tolist(),
                    "reason": reason,
                }

                return (
                    True,
                    {
                        "side": "sell",
                        "qty": str(position),
                        "type": "market",
                    },
                )

        return False, {}
