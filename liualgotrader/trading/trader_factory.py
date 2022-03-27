from typing import Dict

from liualgotrader.common import config
from liualgotrader.common.types import BrokerType
from liualgotrader.trading.alpaca import AlpacaTrader
from liualgotrader.trading.base import Trader
from liualgotrader.trading.gemini import GeminiTrader
from liualgotrader.trading.tradier import TradierTrader

traders: Dict[str, Trader] = {}


def trader_factory(*args, **kwargs) -> Trader:
    global traders

    if config.broker == BrokerType.alpaca:
        if "ALPACA" not in traders:
            traders["ALPACA"] = AlpacaTrader(*args, **kwargs)
        return traders["ALPACA"]
    elif config.broker == BrokerType.gemini:
        if "GEMINI" not in traders:
            traders["GEMINI"] = GeminiTrader(*args, **kwargs)
        return traders["GEMINI"]
    elif config.broker == BrokerType.tradier:
        if "TRADIER" not in traders:
            traders["TRADIER"] = TradierTrader(*args, **kwargs)
        return traders["TradierTrader"]
    else:
        raise Exception(f"unsupported broker  {config.broker}")


def get_trader_by_name(trader_name: str) -> Trader:
    global traders

    if trader_name not in traders:
        raise ValueError(f"Trader {trader_name} was not initialized")

    return traders[trader_name]
