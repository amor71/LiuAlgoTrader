from typing import List

from liualgotrader.common.types import QueueMapper, WSEventType


class StreamingAPI:
    __instance: object = None

    def __init__(self, queues: QueueMapper):
        self.queues = queues
        StreamingAPI.__instance = self

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        pass

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            raise AssertionError("Must instantiate before usage")

        return cls.__instance  # type: ignore

    async def unsubscribe(self, symbol: str) -> bool:
        pass

    async def run(self):
        pass

    async def close(self) -> None:
        pass
