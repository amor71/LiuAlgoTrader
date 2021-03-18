from abc import ABCMeta, abstractmethod
from typing import List

from liualgotrader.common.types import QueueMapper


class Trader(metaclass=ABCMeta):
    def __init__(self, queues: QueueMapper):
        self.queue = QueueMapper

    def __repr__(self):
        return type(self).__name__

    @abstractmethod
    async def get_tradeable_symbols(self) -> List[str]:
        return []

    @abstractmethod
    async def get_shortable_symbols(self) -> List[str]:
        pass
