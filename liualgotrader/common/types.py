from enum import Enum


class DataConnectorType(Enum):
    polygon = 1
    alpaca = 2
    finhub = 3


class TimeScale(Enum):
    day = 24 * 60 * 60
    minute = 60


class WSEventType(Enum):
    TRADE = 1
    QUOTE = 2
    MIN_AGG = 3
    SEC_AGG = 4
