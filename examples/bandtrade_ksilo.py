import asyncio
import sys
import uuid
import contextvars
from datetime import datetime, time, timedelta
from typing import Dict, List, Tuple

import alpaca_trade_api as tradeapi
import numpy as np
import pandas as pd
from liualgotrader.common.data_loader import DataLoader
from liualgotrader.common.tlog import tlog
from liualgotrader.strategies.base import (symbol_var, position_var,
                                           shortable_var, minute_history_var,
                                           symbols_position_var, return_var)
from liualgotrader.common.trading_data import (buy_indicators, buy_time,
                                               cool_down, last_used_strategy,
                                               latest_cost_basis,
                                               latest_scalp_basis, open_orders,
                                               sell_indicators, stop_prices,
                                               target_prices)
from liualgotrader.common.types import AssetType
from liualgotrader.fincalcs.support_resistance import find_stop
from liualgotrader.models.accounts import Accounts
from liualgotrader.models.portfolio import Portfolio
from liualgotrader.strategies.base import Strategy, StrategyType
from liualgotrader.trading.base import Trader
from pandas import DataFrame as df
from pytz import timezone
from talib import BBANDS, MACD, RSI, MA_Type


class BandTrade(Strategy):
    def __init__(
        self,
        batch_id: str,
        data_loader: DataLoader,
        portfolio_id: str,
        ref_run_id: int = None,
    ):
        self.name = type(self).__name__
        self.portfolio_id = portfolio_id
        self.asset_type: AssetType
        super().__init__(
            name=type(self).__name__,
            type=StrategyType.SWING,
            batch_id=batch_id,
            ref_run_id=ref_run_id,
            schedule=[],
            data_loader=data_loader,
            fractional=True,
        )

    async def buy_callback(
        self,
        symbol: str,
        price: float,
        qty: float,
        now: datetime = None,
        trade_fee: float = 0.0,
    ) -> None:
        if self.account_id:
            amount_to_withdraw = price * qty
            if not await Accounts.check_if_enough_balance_to_withdraw(
                self.account_id, amount_to_withdraw + trade_fee
            ):
                raise AssertionError(
                    f"account {self.account_id} does not have enough balance for transaction"
                )

            await Accounts.add_transaction(
                account_id=self.account_id,
                amount=-amount_to_withdraw,
                tstamp=now,
            )
            await Accounts.add_transaction(
                account_id=self.account_id, amount=-trade_fee, tstamp=now
            )
            print(
                "buy",
                -price * qty,
                "fee",
                trade_fee,
                "balance post buy",
                await Accounts.get_balance(self.account_id),
            )

    async def sell_callback(
        self,
        symbol: str,
        price: float,
        qty: float,
        now: datetime = None,
        trade_fee: float = 0.0,
    ) -> None:
        if self.account_id:
            if not await Accounts.check_if_enough_balance_to_withdraw(
                self.account_id, trade_fee
            ):
                raise AssertionError(
                    f"account {self.account_id} does not have enough balance for transaction"
                )

            await Accounts.add_transaction(
                account_id=self.account_id, amount=-trade_fee, tstamp=now
            )
            await Accounts.add_transaction(
                account_id=self.account_id, amount=price * qty, tstamp=now
            )
            print(
                "sell",
                price * qty,
                "fee",
                trade_fee,
                "balance post sell",
                await Accounts.get_balance(self.account_id),
            )

    async def create(self) -> bool:
        if not await super().create():
            return False

        tlog(f"strategy {self.name} created")
        try:
            await Portfolio.associate_batch_id_to_profile(
                portfolio_id=self.portfolio_id, batch_id=self.batch_id
            )
        except Exception:
            tlog("Probably already associated...")
            return False

        portfolio = await Portfolio.load_by_portfolio_id(self.portfolio_id)
        self.account_id = portfolio.account_id
        self.portfolio_size = portfolio.portfolio_size
        self.asset_type = portfolio.asset_type

        return True

    async def is_buy_time(self, now: datetime):
        return (
            time(hour=14, minute=30) >= now.time() >= time(hour=9, minute=30)
            if self.asset_type == AssetType.US_EQUITIES
            else True
        )

    async def is_sell_time(self, now: datetime):
        return True

    def calc_close(self, symbol: str, data_loader: DataLoader, now: datetime):
        serie = (
            (
                self.data_loader[symbol]
                .close[now - timedelta(days=30) : now]  # type:ignore
                .between_time("9:30", "16:00")
            )
            if self.asset_type == AssetType.US_EQUITIES
            else self.data_loader[symbol].close[
                now - timedelta(days=10) : now  # type:ignore
            ]
        )

        if not len(serie):
            serie = self.data_loader[symbol].close[
                now - timedelta(days=30) : now  # type:ignore
            ]

        return (
            serie.resample("1D").last().dropna()
            if self.asset_type == AssetType.US_EQUITIES
            else serie.resample("15min").last().dropna()
        )

    async def handle_buy_side(
        self,
        symbols_position: Dict[str, float],
        data_loader: DataLoader,
        now: datetime,
        trade_fee_precentage: float,
    ) -> Dict[str, Dict]:
        actions = {}

        for symbol, position in symbols_position.items():
            if position != 0:
                continue

            current_price = data_loader[symbol].close[now]
            tlog(f"{symbol} -> {current_price}")
            resampled_close = self.calc_close(symbol, data_loader, now)
            bband = BBANDS(
                resampled_close,
                timeperiod=7,
                nbdevdn=1,
                nbdevup=1,
                matype=MA_Type.EMA,
            )

            yesterday_lower_band = bband[2][-2]
            today_lower_band = bband[2][-1]
            yesterday_close = resampled_close[-2]

            today_open = self.data_loader[symbol].open[
                now.replace(hour=9, minute=30, second=0, microsecond=0)
            ]

            print(
                f"\nyesterday_close < yesterday_lower_band : {yesterday_close < yesterday_lower_band}({yesterday_close} < {yesterday_lower_band})"
            )
            print(
                f"today_open > yesterday_close :{today_open > yesterday_close}({today_open} > {yesterday_close})"
            )
            print(
                f"current_price > today_lower_band :{current_price > today_lower_band}({current_price} > {today_lower_band})"
            )

            if (
                yesterday_close < yesterday_lower_band
                and today_open > yesterday_close
                and current_price > today_lower_band
            ):
                yesterday_upper_band = bband[0][-2]
                if current_price > yesterday_upper_band:
                    return {}

                buy_indicators[symbol] = {
                    "lower_band": bband[2][-2:].tolist(),
                }
                shares_to_buy = await self.calc_qty(
                    current_price,
                    trade_fee_precentage,
                )
                tlog(
                    f"[{self.name}][{now}] Submitting buy for {shares_to_buy} shares of {symbol} at {current_price}"
                )
                tlog(f"indicators:{buy_indicators[symbol]}")
                actions[symbol] = {
                    "side": "buy",
                    "qty": str(shares_to_buy),
                    "type": "limit",
                    "limit_price": str(current_price),
                }

        return actions

    async def handle_sell_side(
        self,
        symbols_position: Dict[str, float],
        data_loader: DataLoader,
        now: datetime,
        trade_fee_precentage: float,
    ) -> Dict[str, Dict]:
        actions = {}

        for symbol, position in symbols_position.items():
            if position == 0:
                continue

            current_price = data_loader[symbol].close[now]
            resampled_close = self.calc_close(symbol, data_loader, now)
            bband = BBANDS(
                resampled_close,
                timeperiod=7,
                nbdevdn=1,
                nbdevup=1,
                matype=MA_Type.EMA,
            )

            yesterday_upper_band = bband[0][-2]

            print(
                f"\ncurrent_price > yesterday_upper_band : {current_price > yesterday_upper_band}({current_price} < {yesterday_upper_band})"
            )

            if current_price > yesterday_upper_band:
                sell_indicators[symbol] = {
                    "upper_band": bband[0][-2:].tolist(),
                    "lower_band": bband[2][-2:].tolist(),
                }

                tlog(
                    f"[{self.name}][{now}] Submitting sell for {position} shares of {symbol} at market"
                )
                tlog(f"indicators:{sell_indicators[symbol]}")
                actions[symbol] = {
                    "side": "sell",
                    "qty": str(position),
                    "type": "limit",
                    "limit_price": str(current_price),
                }

        return actions

    async def should_run_all(self):
        return False

    async def run(
        self,
        # symbol: str,
        now: datetime,
        # position: float = None,
        portfolio_value: float = None,
        debug: bool = False,
        backtesting: bool = False,
        # minute_history: pd.DataFrame = None,
        # shortable: bool = False,
        data_loader=None,
        trader=None,
        fee_buy_percentage: float = 0.0,
        fee_sell_percentage: float = 0.0
    ) -> Tuple[bool, Dict]:
        symbols_position = symbols_position_var.get()
        actions = {}
        await self.setting_context_return(actions, symbol_var.get())
        if await self.is_buy_time(now) and not open_orders:
            actions.update(
                await self.handle_buy_side(
                    symbols_position=symbols_position,
                    data_loader=self.data_loader,
                    now=now,
                    trade_fee_precentage=fee_buy_percentage / 100.0,
                )
            )

        if (
            await self.is_sell_time(now)
            and (
                len(symbols_position)
                or any(symbols_position[x] for x in symbols_position)
            )
            and not open_orders
        ):
            actions.update(
                await self.handle_sell_side(
                    symbols_position=symbols_position,
                    data_loader=self.data_loader,
                    now=now,
                    trade_fee_precentage=fee_sell_percentage / 100.0,
                )
            )
        # return (True, actions[symbol]) if symbol in actions else (False, {})
        return return_var.get()
