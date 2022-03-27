import asyncio

import pytest

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import DataConnectorType
from liualgotrader.scanners.momentum import Momentum
from liualgotrader.trading.trader_factory import trader_factory


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_scanner_alpaca() -> bool:
    print("test_scanner_alpaca")

    config.debug_enabled = False
    dl = DataLoader(connector=DataConnectorType.alpaca)
    trader = trader_factory()
    scanner = Momentum(
        recurrence=None,
        target_strategy_name=None,
        data_loader=dl,
        trading_api=trader,
        max_share_price=500,
        min_share_price=0,
        min_last_dv=3,
        today_change_percent=5,
        min_volume=50000,
        from_market_open=0,
    )

    symbols = await scanner.run()

    print(symbols)
    return True


@pytest.mark.asyncio
async def no_test_scanner_polygon() -> bool:
    print("test_scanner_polygon")

    config.debug_enabled = True
    dl = DataLoader(connector=DataConnectorType.polygon)
    trader = trader_factory()
    scanner = Momentum(
        recurrence=None,
        target_strategy_name=None,
        data_loader=dl,
        trading_api=trader,
        max_share_price=500,
        min_share_price=0,
        min_last_dv=3,
        today_change_percent=5,
        min_volume=50000,
        from_market_open=0,
    )

    symbols = await scanner.run()

    print(symbols)
    return True
