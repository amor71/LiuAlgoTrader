from enum import Enum, auto
from multiprocessing import Queue
from typing import Awaitable, List


class WSConnectState(Enum):
    NOT_CONNECTED = auto()
    CONNECTED = auto()
    AUTHENTICATED = auto()


class StreamingBase:
    def __init__(self, queues: List[Queue]):
        self.queues = queues

    async def subscribe(self, symbol: str, handler: Awaitable) -> bool:
        pass

    async def unsubscribe(self, symbol: str) -> bool:
        pass

    async def close(
        self,
    ) -> None:
        pass
