from datetime import datetime, timedelta
from typing import List, Optional

import alpaca_trade_api as tradeapi


class Scanner:
    def __init__(
        self, name: str, recurrence: Optional[timedelta], data_api: tradeapi
    ):
        self.name = name
        self.recurrence = recurrence
        self.data_api = data_api

    def run(self) -> List[str]:
        return []

    @classmethod
    def get_supported_scanners(cls):
        return ["momentum"]
