from enum import Enum, auto
from multiprocessing import Queue
from typing import Dict


class DataConnectorType(Enum):
    polygon = 1
    alpaca = 2
    # finhub = 3


class BrokerType(Enum):
    alpaca = 1


class TimeScale(Enum):
    day = 24 * 60 * 60
    minute = 60


class WSEventType(Enum):
    TRADE = auto()
    QUOTE = auto()
    MIN_AGG = auto()
    SEC_AGG = auto()


class WSConnectState(Enum):
    NOT_CONNECTED = auto()
    CONNECTED = auto()
    AUTHENTICATED = auto()


class QueueMapper:
    def __init__(self):
        self.queues: Dict[str, Queue] = {}

    def __repr__(self):
        return str(list(self.queues.keys()))

    def __getitem__(self, key: str) -> Queue:
        try:
            return self.queues[key]
        except KeyError:
            raise AssertionError(f"No queue exists for symbol {key}")

    def __setitem__(self, key: str, newvalue: Queue):
        self.queues[key] = newvalue
