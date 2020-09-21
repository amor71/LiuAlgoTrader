from abc import ABCMeta, abstractmethod


class Miner(metaclass=ABCMeta):
    def __init__(
        self,
        name: str,
    ):
        self._name = name

    @property
    def name(self):
        return self._name

    @abstractmethod
    async def run(self) -> bool:
        pass
