from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
from google.cloud import error_reporting
from pandas import DataFrame as df
from talib import MACD, RSI

from common import config
from common.market_data import prev_closes, volume_today
from common.tlog import tlog
from common.trading_data import (buy_indicators, latest_cost_basis,
                                 open_order_strategy, open_orders,
                                 sell_indicators, stop_prices, target_prices)
from fincalcs.support_resistance import find_resistances, find_supports

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
                if rsi[-1] > 76:
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
        self, symbol: str, close: float, minute_history: df, now: datetime
    ) -> Tuple[
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[List[float]],
        Optional[List[float]],
    ]:
        supports = find_supports(
            symbol=symbol,
            strategy_name=self.name,
            current_value=close,
            minute_history=minute_history,
        )
        resistances = find_resistances(
            symbol=symbol,
            strategy_name=self.name,
            current_value=close,
            minute_history=minute_history,
        )
        if supports is None or len(supports) == 0:
            return None, None, None, None, None
        if resistances is None or len(resistances) == 0:
            return None, None, None, None, None

        target_price = supports[-1] + 0.02
        stop_price = resistances[-1] - 0.02
        distance_to_stop = (stop_price - close) / close

        return (
            target_price,
            stop_price,
            distance_to_stop,
            supports,
            resistances,
        )

    async def is_not_shortable(self, symbol: str) -> bool:
        asset = self.trading_api.get_asset(symbol)
        return (
            True
            if asset.tradable is False
            or asset.shortable is False
            or asset.status == "inactive"
            or asset.easy_to_borrow is False
            else False
        )

    async def run(
        self, symbol: str, position: int, minute_history: df, now: datetime
    ) -> bool:
        data = minute_history.iloc[-1]
        if await super().is_buy_time(now) and not position:
            to_buy, indicators = await self._check_buy_signal(
                symbol=symbol,
                open=data.open,
                close=data.close,
                minute_history=minute_history,
            )
            if not to_buy:
                return False

            (
                target_price,
                stop_price,
                distance_to_stop,
                supports,
                resistances,
            ) = await self._find_target_stop_prices(
                symbol=symbol,
                close=data.close,
                minute_history=minute_history,
                now=now,
            )
            if target_price is None or stop_price is None:
                return False

            portfolio_value = float(
                self.trading_api.get_account().portfolio_value
            )
            shares_to_buy = (
                portfolio_value * config.risk // data.close
            ) - position
            if shares_to_buy <= 0:
                return False

            if await self.is_not_shortable(symbol):
                tlog(f"{self.name}\t\t\tcannot short {symbol}.")
                return False

            tlog(
                f"[{self.name}]\t\t\tSubmitting short sell for {shares_to_buy} shares of {symbol} at {data.close} target {target_price} stop {stop_price} distance_to_stop {distance_to_stop}"
            )

            indicators.update(
                {
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "distance_to_stop": distance_to_stop,
                    "supports": supports,
                    "resistances": resistances,
                }
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

        elif await super().is_sell_time(now) and position < 0:
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
                sell_reasons.append("target")
            elif rsi[-1] <= 30.0:
                to_sell = True
                sell_reasons.append("low RSI")

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
