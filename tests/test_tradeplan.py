import asyncio
import uuid
from datetime import datetime, timedelta

import pytest

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.consumer import create_strategies_from_db
from liualgotrader.models.tradeplan import TradePlan
from liualgotrader.trading.trader_factory import trader_factory


@pytest.fixture
def event_loop():
    config.build_label = "pytest"
    loop = asyncio.new_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_load_trade_plan_from_db():
    trade_plan = await TradePlan.load()

    for plan in trade_plan:
        print(plan)

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_load_testplan_from_db():

    try:
        strategy_list = await create_strategies_from_db(
            batch_id=str(uuid.uuid4()),
            trader=trader_factory(),
            data_loader=DataLoader(),
        )
    except FileNotFoundError as e:
        print(f"FileNotFoundError {e}")
        return True

    print(strategy_list)

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_new_entries():
    trade_plan = await TradePlan.get_new_entries(
        since=datetime.utcnow() - timedelta(days=5)
    )

    for plan in trade_plan:
        print(plan)

    return True
