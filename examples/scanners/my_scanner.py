"""my_scanner.py: custom scanner implementing the Scanner class"""
from datetime import datetime, timedelta
from typing import List, Optional

from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.scanners.base import Scanner


class MyScanner(Scanner):
    def __init__(self, data_loader: DataLoader, **kwargs):
        super().__init__(
            name=type(self).__name__,
            recurrence=kwargs.get("recurrence"),
            data_loader=data_loader,
            target_strategy_name=kwargs.get("target_strategy_name"),
        )

    async def run(self, back_time: datetime = None) -> List[str]:
        return ["AAPL"]
