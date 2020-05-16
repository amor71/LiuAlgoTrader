from enum import Enum, auto
from typing import Awaitable


class WSConnectState(Enum):
    NOT_CONNECTED = auto()
    CONNECTED = auto()
    AUTHENTICATED = auto()


class StreamingBase:
    def __init__(self):
        pass

    async def subscribe(self, symbol: str, handler: Awaitable) -> bool:
        pass

    async def unsubscribe(self, symbol: str) -> bool:
        pass
