from datetime import datetime, timedelta
from typing import Any, Dict, Tuple

import alpaca_trade_api as tradeapi
from google.cloud import error_reporting
from pandas import DataFrame as df
from talib import MACD, RSI

import config
from market_data import prev_closes, volume_today
from support_resistance import find_resistances, find_supports
from tlog import tlog
from trading_data import (buy_indicators, latest_cost_basis,
                          open_order_strategy, open_orders, sell_indicators,
                          stop_prices, target_prices)

from .base import Strategy

error_logger = error_reporting.Client()


class MomentumShort(Strategy):
    name = "momentum_short"

    def __init__(self, trading_api: tradeapi, data_api: tradeapi):
        super().__init__(
            name=self.name, trading_api=trading_api, data_api=data_api
        )

    async def create(self) -> None:
        await super().create()
        tlog(f"strategy {self.name} created")

    async def _check_buy_signal(
        self, symbol: str, open: float, close: float, minute_history: df
    ) -> Tuple[bool, Dict]:
        # See how high the price went during the first 15 minutes
        if not config.bypass_market_schedule:
            lbound = config.market_open
            ubound = lbound + timedelta(minutes=15)
            try:
                high_15m = minute_history.loc[lbound:ubound]["high"].max()  # type: ignore
            except Exception:
                error_logger.report_exception()
                # Because we're aggregating on the fly, sometimes the datetime
                # index can get messy until it's healed by the minute bars
                return False, {}
        else:
            high_15m = prev_closes[symbol]

        # Get the change since yesterday's market close
        daily_pct_change = (close - prev_closes[symbol]) / prev_closes[symbol]

        if (
            daily_pct_change > 0.04
            and close > high_15m
            and volume_today[symbol] > 30000
        ):
            #               tlog(
            #                    f"[{self.name}] {symbol} high_15m={high_15m} data.close={data.close}"
            #                )
            # check for a positive, increasing MACD
            macds = MACD(
                minute_history["close"].dropna().between_time("9:30", "16:00")
            )

            macd = macds[0]
            macd_signal = macds[1]
            if (
                macd[-1].round(2) > 0
                and macd[-3].round(3) < macd[-2].round(3) < macd[-1].round(3)
                and macd[-1].round(2) > macd_signal[-1].round(2)
                and close > open
            ):
                tlog(
                    f"[{self.name}]\tMACD(12,26) for {symbol} trending up and above signals"
                )

                # check RSI is high enough
                rsi = RSI(minute_history["close"], 14)
                tlog(f"[{self.name}]\t\tRSI for {symbol}={round(rsi[-1], 2)}")
                if rsi[-1] > 75:
                    tlog(f"[{self.name}]\t\tRSI for {symbol} is above signal")
                    return (
                        True,
                        {
                            "rsi": rsi[-1].tolist(),
                            "macd": macd[-5:].tolist(),
                            "macd_signal": macd_signal[-5:].tolist(),
                        },
                    )

        return False, {}

    async def _find_target_stop_prices(
        self, close: float, minute_history: df, now: datetime
    ) -> Any[Tuple[None, None], Tuple[float, float]]:
        supports = find_supports(
            strategy_name=self.name,
            current_value=close,
            minute_history=minute_history,
            now=now,
        )
        resistances = find_resistances(
            strategy_name=self.name,
            current_value=close,
            minute_history=minute_history,
            now=now,
        )
        if supports is None or len(supports) == 0:
            return None, None
        if resistances is None or len(resistances) == 0:
            return None, None

        target_price = supports[-1]
        stop_price = resistances[-1]
        distance_to_stop = (stop_price - close) / close

        if distance_to_stop < 0.02:
            return False

        return target_price, stop_price

    async def is_not_shortable(self, symbol: str) -> bool:
        asset = self.trading_api.get_asset(symbol)
        return (
            False
            if asset.tradable is False
            or asset.shortable is False
            or asset.status == "inactive"
            or asset.easy_to_borrow is False
            else True
        )

    async def _is_buy_time(self, now: datetime):
        return (
            True
            if config.trade_buy_window
            > (now - config.market_open).seconds // 60
            > config.market_cool_down_minutes
            or config.bypass_market_schedule
            else False
        )

    async def _is_sell_time(self, now: datetime):
        return (
            True
            if (
                (now - config.market_open).seconds // 60
                >= config.market_cool_down_minutes
                or config.bypass_market_schedule
            )
            and (config.market_close - now).seconds // 60 > 15
            else False
        )

    async def run(
        self, symbol: str, position: int, minute_history: df, now: datetime
    ) -> bool:
        data = minute_history.iloc[-1]
        if await self._is_buy_time(now) and not position:
            to_buy, indicators = await self._check_buy_signal(
                symbol=symbol,
                open=data.open,
                close=data.close,
                minute_history=minute_history,
            )
            if not to_buy:
                return False

            target_price, stop_price = await self._find_target_stop_prices(
                close=data.close, minute_history=minute_history, now=now
            )
            if target_price is None:
                return False

            portfolio_value = float(
                self.trading_api.get_account().portfolio_value
            )
            shares_to_buy = (
                portfolio_value * config.risk // data.close
            ) - position
            if shares_to_buy <= 0:
                return False

            if self.is_not_shortable(symbol):
                tlog(f"{self.name}\t\t\tcannot short {symbol}.")
                return False

            tlog(
                f"[{self.name}]\t\t\tSubmitting short sell for {shares_to_buy} shares of {symbol} at {data.close} target {target_price} stop {stop_price}"
            )
            sell_indicators[symbol] = indicators

            try:
                o = self.trading_api.submit_order(
                    symbol=symbol,
                    qty=str(shares_to_buy),
                    side="sell",
                    type="market",
                    time_in_force="day",
                )
                open_orders[symbol] = (o, "sell_short")
                latest_cost_basis[symbol] = data.close
                target_prices[symbol] = target_price
                stop_prices[symbol] = stop_price
                open_order_strategy[symbol] = self
                return True
            except Exception as e:
                error_logger.report_exception()
                tlog(
                    f"[{self.name}]\t\t\t\tfailed to sell short {symbol} for reason {e}"
                )

        elif await self._is_sell_time(now) and position:
            # Check for liquidation signals
            rsi = RSI(minute_history["close"], 14)
            movement = (
                data.close - latest_cost_basis[symbol]
            ) / latest_cost_basis[symbol]

            to_sell = False
            sell_reasons = []
            if data.close >= stop_prices[symbol]:
                to_sell = True
                sell_reasons.append("stopped")
            elif data.close <= target_prices[symbol]:
                to_sell = True
                sell_reasons.append(f"target")
            elif rsi[-1] <= 30.0:
                to_sell = True
                sell_reasons.append(f"low RSI")

            if to_sell:
                try:
                    buy_indicators[symbol] = {
                        "rsi": rsi[-5:].tolist(),
                        "movement": movement,
                        "reasons": " AND ".join(
                            [str(elem) for elem in sell_reasons]
                        ),
                    }

                    tlog(
                        f"[{self.name}]\tSubmitting short buy for {position} shares of {symbol} at market"
                    )

                    o = self.trading_api.submit_order(
                        symbol=symbol,
                        qty=str(-position),
                        side="buy",
                        type="market",
                        time_in_force="day",
                    )

                    open_orders[symbol] = (o, "buy_short")
                    latest_cost_basis[symbol] = data.close
                    open_order_strategy[symbol] = self
                    return True

                except Exception as e:
                    error_logger.report_exception()
                    tlog(
                        f"[{self.name}]\t\tfailed to buy short {symbol} for reason {e}"
                    )

        return False
