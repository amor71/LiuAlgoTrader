from enum import Enum, auto


class DataConnectorType(Enum):
    polygon = 1
    alpaca = 2
    # finhub = 3


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
