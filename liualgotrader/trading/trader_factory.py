from liualgotrader.common import config
from liualgotrader.common.types import BrokerType
from liualgotrader.trading.alpaca import AlpacaTrader
from liualgotrader.trading.base import Trader


def trader_factory():
    if config.broker == BrokerType.alpaca:
        return AlpacaTrader
    else:
        raise Exception(f"unsupported broker  {config.broker}")
