import asyncio
import uuid

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.strategies.base import Strategy


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
async def test_get_strategy():
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

    return True
