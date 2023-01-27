import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.data.alpaca import AlpacaData


def test_get_trading_day():
    alpaca_data = AlpacaData()

    symbol = "BTC/USD"
    last_trading_time = alpaca_data.get_last_trading(symbol)

    print(f"{symbol} last trading time: {last_trading_time}")
    trading_day = alpaca_data.get_trading_day(symbol, last_trading_time, -1500)

    print(f"{symbol} trading day: {trading_day}")
