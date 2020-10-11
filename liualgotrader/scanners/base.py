from abc import ABCMeta, abstractmethod
from datetime import timedelta, datetime
from typing import List, Optional

import alpaca_trade_api as tradeapi


class Scanner(metaclass=ABCMeta):
    def __init__(
        self,
        name: str,
        data_api: tradeapi,
        recurrence: Optional[timedelta],
        target_strategy_name: Optional[str],
        data_source: object = None,
    ):
        self.name = name
        self.recurrence = recurrence
        self.target_strategy_name = target_strategy_name
        self.data_api = data_api
        self.data_source = data_source

    @abstractmethod
    async def run(self, back_time: datetime = None) -> List[str]:
        return []

    @classmethod
    def get_supported_scanners(cls):
        return ["momentum"]
