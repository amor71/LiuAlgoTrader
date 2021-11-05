from liualgotrader.common import config
from liualgotrader.common.types import BrokerType
from liualgotrader.trading.alpaca import AlpacaTrader
from liualgotrader.trading.gemini import GeminiTrader


def trader_factory():
    if config.broker == BrokerType.alpaca:
        return AlpacaTrader
    elif config.broker == BrokerType.gemini:
        return GeminiTrader
    else:
        raise Exception(f"unsupported broker  {config.broker}")
