import asyncio
import uuid
from datetime import date

import pytest

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import AssetType, TimeScale
from liualgotrader.enhanced_backtest import backtest_time_range
from liualgotrader.scanners.base import Scanner
from liualgotrader.strategies.base import Strategy


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_backtest_day():
    print("*** test_backtest_day ***")
    config.debug_enabled = False
    dl = DataLoader(scale=TimeScale.day)

    c = await Scanner.get_scanner(
        dl,
        "MyScanner",
        {
            "filename": "./examples/scanners/my_scanner.py",
        },
    )

    if not c:
        raise AssertionError("Failed to instantiate scanner")

    print(f"Loaded scanner {c.name}")

    s = await Strategy.get_strategy(
        batch_id=str(uuid.uuid4()),
        strategy_name="MyStrategy",
        strategy_details={
            "filename": "./examples/skeleton-strategy/my_strategy.py",
            "schedule": [],
        },
    )

    if not s:
        raise AssertionError("Failed to instantiate strategy")

    print(f"Loaded strategy {s.name}")

    await backtest_time_range(
        from_date=date(year=2020, month=10, day=1),
        to_date=date(year=2020, month=11, day=1),
        scale=TimeScale.day,
        buy_fee_percentage=0,
        sell_fee_percentage=0,
        data_loader=dl,
        asset_type=AssetType.US_EQUITIES,
        strategies=[s],
        scanners=[c],
    )

    return True


@pytest.mark.asyncio
async def test_backtest_min():
    print("*** test_backtest_min ***")
    config.debug_enabled = False
    dl = DataLoader(scale=TimeScale.minute)

    c = await Scanner.get_scanner(
        dl,
        "MyScanner",
        {
            "filename": "./examples/scanners/my_scanner.py",
        },
    )

    if not c:
        raise AssertionError("Failed to instantiate scanner")

    print(f"Loaded scanner {c.name}")

    s = await Strategy.get_strategy(
        batch_id=str(uuid.uuid4()),
        strategy_name="MyStrategy",
        strategy_details={
            "filename": "./examples/skeleton-strategy/my_strategy.py",
            "schedule": [],
        },
    )

    if not s:
        raise AssertionError("Failed to instantiate strategy")

    print(f"Loaded strategy {s.name}")

    await backtest_time_range(
        from_date=date(year=2020, month=10, day=1),
        to_date=date(year=2020, month=10, day=3),
        scale=TimeScale.minute,
        buy_fee_percentage=0,
        sell_fee_percentage=0,
        data_loader=dl,
        asset_type=AssetType.US_EQUITIES,
        strategies=[s],
        scanners=[c],
    )

    return True
