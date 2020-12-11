from datetime import date, timedelta
from typing import Dict

from liualgotrader.analytics import consolidate
from liualgotrader.common.tlog import tlog
from liualgotrader.miners.base import Miner
from liualgotrader.models.algo_run import AlgoRun


class Gainloss(Miner):
    def __init__(
        self,
        data: Dict,
        debug=False,
    ):
        try:
            self.days = int(data["days"])
        except Exception:
            raise ValueError(
                "[ERROR] Miner must receive positive `days` parameter"
            )
        super().__init__(name="GainLossMiner")

    async def run(self) -> bool:
        data = await AlgoRun.get_batch_ids(
            start_date=date.today() - timedelta(days=self.days)
        )
        tlog(f"Miner {self.name} will consolidate {len(data)} batches")
        for index, row in data.iterrows():
            tlog(f"{int(index)+1}/{len(data)}")
            await consolidate.trades(row.batch_id)

        return True
