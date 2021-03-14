from multiprocessing import Queue
from typing import Awaitable, Dict, List

from liualgotrader.common.types import WSEventType


class QueueMapper:
    def __init__(self):
        self.queues: Dict[str, Queue] = {}

    def __getitem__(self, key: str) -> Queue:
        try:
            return self.queues[key]
        except KeyError:
            raise AssertionError(f"No queue exists for symbol {key}")

    def __setitem__(self, key: str, newvalue: Queue):
        self.queues[key] = newvalue


class StreamingAPI:
    def __init__(self, queues: QueueMapper):
        self.queues = queues

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        pass

    async def unsubscribe(self, symbol: str) -> bool:
        pass

    async def close(self) -> None:
        pass
