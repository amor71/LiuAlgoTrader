"""follow the gold"""
from datetime import datetime, timedelta
from typing import List, Optional

from liualgotrader.common.data_loader import DataLoader
from liualgotrader.common.tlog import tlog
from liualgotrader.scanners.base import Scanner


class BTCUSD(Scanner):
    name = "BTCUSD"

    def __init__(
        self,
        data_loader: DataLoader,
        recurrence: Optional[timedelta] = None,
        target_strategy_name: str = None,
    ):
        super().__init__(
            name=self.name,
            data_loader=data_loader,
            recurrence=recurrence,
            target_strategy_name=target_strategy_name,
        )

    async def run(self, back_time: datetime = None) -> List[str]:
        if not back_time:
            back_time = datetime.now()

        return ["BTCUSD"]
