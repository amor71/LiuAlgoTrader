import asyncio
from datetime import datetime
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi

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
from liualgotrader.fincalcs.vwap import add_daily_vwap
from liualgotrader.strategies.base import Strategy, StrategyType
from pandas import DataFrame as df
from pandas import Timestamp as ts
from pandas import concat


class VWAPShort(Strategy):
    name = "vwap_short"
    was_above_vwap: Dict = {}

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
        pass

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        latest_cost_basis[symbol] = price

    async def create(self) -> None:
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
        if not shortable:
            return False, {}

        data = minute_history.iloc[-1]

        if data.close > data.average:
            self.was_above_vwap[symbol] = True

        if (
            await super().is_buy_time(now)
            and not position
            and not open_orders.get(symbol, None)
        ):
            if data.average > data.open:
                return False, {}

            day_start = ts(config.market_open)

            try:
                day_start_index = minute_history["close"].index.get_loc(
                    day_start, method="nearest"
                )
            except Exception as e:
                tlog(
                    f"[ERROR]{self.name}[{now}]{symbol} can't load index for {day_start} w/ {e}"
                )
                return False, {}

            close = (
                minute_history["close"][day_start_index:-1]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .last()
            ).dropna()
            open = (
                minute_history["open"][day_start_index:-1]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .first()
            ).dropna()
            high = (
                minute_history["high"][day_start_index:-1]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .max()
            ).dropna()
            low = (
                minute_history["low"][day_start_index:-1]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .min()
            ).dropna()
            volume = (
                minute_history["volume"][day_start_index:-1]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .sum()
            ).dropna()

            df = concat(
                [
                    open.rename("open"),
                    high.rename("high"),
                    low.rename("low"),
                    close.rename("close"),
                    volume.rename("volume"),
                ],
                axis=1,
            )
            if not add_daily_vwap(df):
                tlog(f"[{now}]{symbol} failed in add_daily_vwap")
                return False, {}

            vwap_series = df["average"]

            if (
                data.close < vwap_series[-1] * 0.99
                and self.was_above_vwap.get(symbol, False)
                and close[-1] < open[-1] <= close[-2] < open[-2] <= close[-3] < open[-3]
            ):

                stop_price = vwap_series[-1]
                target_price = data.close - 3 * (stop_price - data.close)

                stop_prices[symbol] = stop_price
                target_prices[symbol] = target_price

                if portfolio_value is None:
                    if trading_api:
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
                            tlog(
                                "f[{symbol}][{now}[Error] failed to get portfolio_value"
                            )
                            return False, {}
                    else:
                        raise Exception(
                            f"{self.name}: both portfolio_value and trading_api can't be None"
                        )

                shares_to_buy = (
                    portfolio_value * config.risk // (data.close - stop_prices[symbol])
                )
                if not shares_to_buy:
                    shares_to_buy = 1

                buy_price = data.close
                tlog(
                    f"[{self.name}][{now}] Submitting buy short for {-shares_to_buy} shares of {symbol} at {buy_price} target {target_prices[symbol]} stop {stop_prices[symbol]}"
                )

                sell_indicators[symbol] = {
                    "vwap_series": vwap_series[-5:].tolist(),
                    "vwap": data.vwap,
                    "avg": data.average,
                }

                return (
                    True,
                    {
                        "side": "sell",
                        "qty": str(-shares_to_buy),
                        "type": "market",
                    },
                )

        if (
            await super().is_sell_time(now)
            and position
            and last_used_strategy[symbol].name == self.name
            and not open_orders.get(symbol)
        ):
            day_start = ts(config.market_open)
            day_start_index = minute_history["close"].index.get_loc(
                day_start, method="nearest"
            )
            close = (
                minute_history["close"][day_start_index:-1]
                .dropna()
                .between_time("9:30", "16:00")
                .resample("5min")
                .last()
            ).dropna()
            to_sell: bool = False
            reason: str = ""

            if data.close >= stop_prices[symbol]:
                to_sell = True
                reason = "stopped"
            elif data.close <= target_prices[symbol]:
                to_sell = True
                reason = "target reached"
            elif close[-1] > close[-2] > close[-3] < close[-4]:
                to_sell = True
                reason = "reversing direction"

            if to_sell:
                buy_indicators[symbol] = {
                    "close_5m": close[-5:].tolist(),
                    "reason": reason,
                }

                tlog(
                    f"[{self.name}][{now}] Submitting sell short for {position} shares of {symbol} at market {data.close} with reason:{reason}"
                )
                return (
                    True,
                    {
                        "side": "buy",
                        "qty": str(-position),
                        "type": "market",
                    },
                )

        return False, {}
