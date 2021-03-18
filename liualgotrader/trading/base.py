import asyncio
from typing import List, Optional

from liualgotrader.common.types import QueueMapper


class Trader:
    __instance: object = None

    def __init__(self, queues: QueueMapper):
        self.queues = queues
        Trader.__instance = self

    def __repr__(self):
        return type(self).__name__

    async def get_tradeable_symbols(self) -> List[str]:
        pass

    async def get_shortable_symbols(self) -> List[str]:
        pass

    async def run(self) -> Optional[asyncio.Task]:
        pass

    @classmethod
    def get_instance(cls):
        if not cls.__instance:
            raise AssertionError("Must instantiate before usage")

        return cls.__instance  # type: ignore
