from enum import Enum, auto
from typing import Dict, List, Optional

from mnqueues import MNQueue


class DataConnectorType(Enum):
    polygon = 1
    alpaca = 2
    finnhub = 3


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
    def __init__(self, queue_list: List[MNQueue] = None):
        self.queues: Dict[str, MNQueue] = {}
        self.queue_list: Optional[List[MNQueue]] = queue_list

    def __repr__(self):
        return str(list(self.queues.keys()))

    def __getitem__(self, key: str) -> MNQueue:
        try:
            return self.queues[key]
        except KeyError:
            raise AssertionError(f"No queue exists for symbol {key}")

    def __setitem__(self, key: str, newvalue: MNQueue):
        if self.queue_list and newvalue not in self.queue_list:
            raise AssertionError(f"key {key} added to unknown Queue")
        self.queues[key] = newvalue

    def get_allqueues(self) -> Optional[List[MNQueue]]:
        return self.queue_list
