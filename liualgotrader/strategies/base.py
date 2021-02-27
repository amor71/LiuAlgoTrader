"""Base Class for Strategies"""
import importlib
import traceback
from abc import ABCMeta, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
from pandas import DataFrame as df

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader
from liualgotrader.common.tlog import tlog
from liualgotrader.models.algo_run import AlgoRun


class StrategyType(Enum):
    DAY_TRADE = 1
    SWING = 2


class Strategy(metaclass=ABCMeta):
    def __init__(
        self,
        name: str,
        type: StrategyType,
        batch_id: str,
        schedule: List[Dict],
        ref_run_id: int = None,
        dl: DataLoader = None,
    ):
        self.name = name
        self.type = type
        self.ref_run_id = ref_run_id
        self.algo_run = AlgoRun(strategy_name=self.name, batch_id=batch_id)
        self.schedule = schedule
        self.dl = dl

    def __repr__(self):
        return self.name

    async def create(self):
        await self.algo_run.save(
            pool=config.db_conn_pool, ref_algo_run_id=self.ref_run_id
        )

    @abstractmethod
    async def run(
        self,
        symbol: str,
        shortable: bool,
        position: int,
        now: datetime,
        minute_history: df = None,
        portfolio_value: float = None,
        trading_api: tradeapi = None,
        debug: bool = False,
        backtesting: bool = False,
    ) -> Tuple[bool, Dict]:
        return False, {}

    async def is_sell_time(self, now: datetime):
        return (
            True
            if (
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
            else False
        )

    async def is_buy_time(self, now: datetime):
        return (
            True
            if any(
                schedule["duration"]
                > (now - config.market_open).seconds // 60
                > schedule["start"]
                for schedule in self.schedule
            )
            or (
                hasattr(config, "bypass_market_schedule")
                and config.bypass_market_schedule
            )
            else False
        )

    async def buy_callback(self, symbol: str, price: float, qty: int) -> None:
        pass

    async def sell_callback(self, symbol: str, price: float, qty: int) -> None:
        pass

    @classmethod
    async def get_strategy(
        cls,
        batch_id: str,
        strategy_name: str,
        strategy_details: Dict,
        dl: DataLoader = None,
        ref_run_id: Optional[int] = None,
    ):
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
                dl=dl,
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
