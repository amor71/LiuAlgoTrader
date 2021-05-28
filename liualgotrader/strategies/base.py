"""Base Class for Strategies"""
import asyncio
import importlib
import traceback
from abc import ABCMeta, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.tlog import tlog
from liualgotrader.models.algo_run import AlgoRun
from liualgotrader.models.keystore import KeyStore


class StrategyType(Enum):
    DAY_TRADE = 1
    SWING = 2


class Strategy(object):
    def __init__(
        self,
        name: str,
        type: StrategyType,
        batch_id: str,
        schedule: List[Dict],
        ref_run_id: int = None,
        data_loader: DataLoader = None,
    ):
        """Strategy default initialization, should be called by all Strategy objects.

        Keyword arguments:
        name: Strategy name, used in the `tradeplan.toml` file,
        type: Strategy type (= day-trade / swing),
        batch_id: generated by the platform, used to group executions,
        schedule: execution time, a defined in the .toml file, note it's mandatory to include,
                  may have more than one execution window. Execution winodows are not enforced
                  by the platform.
        ref_run_id : Used for back-testing,
        data_loader: Passed by the framework, used like a DataFrame to access symbol data.
        """

        self.name = name
        self.batch_id = batch_id
        self.type = type
        self.ref_run_id = ref_run_id
        self.algo_run = AlgoRun(strategy_name=self.name, batch_id=batch_id)
        self.schedule = schedule
        self.data_loader = data_loader
        self.global_var: Dict = {}

    def __repr__(self):
        return self.name

    async def create(self) -> bool:
        """Called by the framework upon instantiation. Must always call super() implementation.

        Return Values:
        If create returns False, the platform will not execute the Strategy. This is helpful
        specifically for situations when multiple processes are running, yet a strategy
        would like to execute a single copy only.
        """
        await self.algo_run.save(
            pool=config.db_conn_pool, ref_algo_run_id=self.ref_run_id
        )
        return True

    async def should_run_all(self):
        """Called by the framework to select if to use the `run_all()` function, or
        `run()` function.
        """
        return False

    async def run_all(
        self,
        symbols_position: Dict[str, int],
        data_loader: DataLoader,
        now: datetime,
        portfolio_value: float = None,
        trading_api: tradeapi = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Dict[str, Dict]:
        """Called by the framework, periodically, if `should_run_all()` returns True. This function,
        unlike `run()` is executed once, and not per symbol.

         Keyword arguments:
         symbols_position: Dictionary, with open position (quantity) per symbol,
         data_loader: Send by the framework, DataFrame like object to accessing symbol data,
         now: current timestamp (may be in the past, if called by backtester),
         portfolio_value: Sent by the framework [TO BE DEPRECATED],
         trading_api: Sent by the framework, provides access to the Trader [TO BE DEPRECATED],
         debug: Debug flag, used mostly in backtesting,
         backtesting: Flag indicating if calling during backtesting session, or real-time

         Returns:
         Dictionary with symbol and 'actions' (see documentation for supported actions)
        """
        return {}

    async def run(
        self,
        symbol: str,
        shortable: bool,
        position: int,
        now: datetime,
        minute_history: df,
        portfolio_value: float = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        """Called by the framework, per symbol.

        Keyword arguments:
        symbol: to act on,
        shortable: [TO BE DEPRECATED],
        position: current position (could be 0),
        now: current time w/ time zone (note can be in the past for backtesting),
        minute_history: DataFrame holding data,
        portfolio_value: [TO BE DEPRECATED],
        debug: Debug flag, used mostly in backtesting,
        backtesting: Flag indicating if calling during backtesting session, or real-time

        Returns:
        False, {} in case no action to be taken,
        True, {action - see documentation for supported actions}
        """
        return False, {}

    async def is_sell_time(self, now: datetime):
        return bool(
            (
                any(
                    (now - config.market_open).seconds // 60
                    >= schedule["start"]
                    for schedule in self.schedule
                )
                or (
                    hasattr(config, "bypass_market_schedule")
                    and config.bypass_market_schedule
                )
            )
            and (config.market_close - now).seconds // 60 > 15
        )

    async def is_buy_time(self, now: datetime):
        return bool(
            any(
                (schedule["duration"] + schedule["start"])
                > (now - config.market_open).seconds // 60
                > schedule["start"]
                for schedule in self.schedule
            )
            or (
                hasattr(config, "bypass_market_schedule")
                and config.bypass_market_schedule
            )
        )

    async def buy_callback(
        self, symbol: str, price: float, qty: int, now: datetime = None
    ) -> None:
        """Called by Framework, upon successful buy (could be partial)"""
        pass

    async def sell_callback(
        self, symbol: str, price: float, qty: int, now: datetime = None
    ) -> None:
        """Called by Framework, upon successful sell (could be partial)"""
        pass

    async def get_global_var(self, key, context):
        """implementing key-store retrival"""
        if key in self.global_var:
            return self.global_var[key]
        else:
            self.global_var[key] = (
                val := await KeyStore.load(key, self.name, context)
            )
            return val

    async def set_global_var(self, key, value, context):
        """implementing key-store storing"""
        self.global_var[key] = value
        await KeyStore.save(key, value, self.name, context)

    @classmethod
    async def get_strategy(
        cls,
        batch_id: str,
        strategy_name: str,
        strategy_details: Dict,
        data_loader: DataLoader = None,
        ref_run_id: Optional[int] = None,
    ):
        """Internal, called by the Platform."""
        try:
            spec = importlib.util.spec_from_file_location(  # type: ignore
                "module.name", strategy_details["filename"]
            )
            custom_strategy_module = importlib.util.module_from_spec(spec)  # type: ignore
            spec.loader.exec_module(custom_strategy_module)  # type: ignore
            class_name = strategy_name

            custom_strategy = getattr(custom_strategy_module, class_name)

            if not issubclass(custom_strategy, Strategy):
                tlog(f"strategy must inherit from class {Strategy.__name__}")
                exit(0)
            strategy_details.pop("filename", None)
            s = custom_strategy(
                batch_id=batch_id,
                ref_run_id=ref_run_id,
                data_loader=data_loader,
                **strategy_details,
            )
            await s.create()
        except FileNotFoundError as e:
            tlog(f"[Error] file not found `{strategy_details['filename']}`")
            exit(0)
        except Exception as e:
            tlog(
                f"[Error]exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()
            exit(0)
        else:
            return s
