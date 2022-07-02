from dataclasses import dataclass
from enum import Enum, auto
from multiprocessing import Queue
from typing import Dict, List, Optional

import pandas as pd


class DataConnectorType(Enum):
    polygon = 1
    alpaca = 2
    finnhub = 3
    gemini = 4
    tradier = 5


class BrokerType(Enum):
    alpaca = 1
    gemini = 2
    tradier = 3


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


class AssetType(Enum):
    US_EQUITIES = auto()
    CRYPTO = auto()


@dataclass
class Order:
    class EventType(Enum):
        partial_fill = auto()
        fill = auto()
        canceled = auto()
        rejected = auto()
        cancel_rejected = auto()
        pending = auto()
        error = auto()
        open = auto()
        other = auto()

    class FillSide(Enum):
        buy = auto()
        sell = auto()

    order_id: str
    symbol: str
    event: EventType
    submitted_at: pd.Timestamp
    price: Optional[float] = None
    trade_fees: Optional[float] = None
    filled_qty: Optional[float] = None
    side: Optional[FillSide] = None
    remaining_amount: Optional[float] = None
    avg_execution_price: Optional[float] = None
    external_account_id: Optional[str] = None


@dataclass
class ThreadFlags:
    run: bool = True


@dataclass
class Trade:
    order_id: str
    symbol: str
    event: Order.EventType
    side: Order.FillSide
    filled_qty: float
    trade_fee: float
    filled_avg_price: float
    liquidity: str
    updated_at: pd.Timestamp


class QueueMapper:
    def __init__(self, queue_list: List[Queue] = None):
        self.queues: Dict[str, Queue] = {}
        self.queue_list: Optional[List[Queue]] = queue_list

    def __repr__(self):
        return str(list(self.queues.keys()))

    def __getitem__(self, key: str) -> Queue:
        try:
            return self.queues[key.lower()]
        except KeyError as e:
            raise AssertionError(f"No queue exists for symbol {key}") from e

    def __setitem__(self, key: str, newvalue: Queue):
        if self.queue_list and newvalue not in self.queue_list:
            raise AssertionError(f"key {key} added to unknown Queue")
        self.queues[key.lower()] = newvalue

    def get_allqueues(self) -> Optional[List[Queue]]:
        return self.queue_list
