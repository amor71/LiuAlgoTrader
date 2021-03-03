from abc import ABCMeta, abstractmethod
from typing import List


class Trader(metaclass=ABCMeta):
    def __init__(
        self,
    ):
        pass

    def __repr__(self):
        return type(self).__name__

    @abstractmethod
    async def get_tradeable_symbols(self) -> List[str]:
        return []

    @abstractmethod
    async def get_shortable_symbols(self) -> List[str]:
        pass
