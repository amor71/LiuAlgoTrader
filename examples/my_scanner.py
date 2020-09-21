"""my_scanner.py: custom scanner implementing the Scanner class"""
from datetime import timedelta
from typing import List, Optional

import alpaca_trade_api as tradeapi

from liualgotrader.scanners.base import Scanner


class MyScanner(Scanner):
    name = "myCustomScanner"

    def __init__(
        self, recurrence: Optional[timedelta], data_api: tradeapi, **args
    ):
        print(args)
        super().__init__(
            name=self.name,
            recurrence=recurrence,
            data_api=data_api,
            target_strategy_name=None,
        )

    async def run(self) -> List[str]:
        return ["APPL"]
