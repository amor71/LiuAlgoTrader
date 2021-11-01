import asyncio
import uuid
from datetime import date

import pandas as pd
import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import AssetType
from liualgotrader.models.portfolio import Portfolio


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_exists_negative() -> bool:
    result = await Portfolio.exists("1234")
    if result == True:
        raise AssertionError("result should be False")
    print(result)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_exists_positive() -> bool:
    id: str = str(uuid.uuid4())
    await Portfolio.save(
        id,
        5000,
        10,
        {},
    )
    result = await Portfolio.exists(id)
    if result == False:
        raise AssertionError(f"result should be True for {id}")

    print(result)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_crypto_1() -> bool:
    id: str = str(uuid.uuid4())
    await Portfolio.save(id, 5000, 10, {}, asset_type=AssetType.CRYPTO)
    result = await Portfolio.exists(id)
    if result == False:
        raise AssertionError(f"result should be True for {id}")

    print(result)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_crypto_2() -> bool:
    id: str = str(uuid.uuid4())
    await Portfolio.save(id, 5000, 10, {}, asset_type=AssetType.CRYPTO)
    result = await Portfolio.exists(id)
    if result == False:
        raise AssertionError(f"result should be True for {id}")

    p = await Portfolio.load_by_portfolio_id(id)
    print(p)
    if p.asset_type != AssetType.CRYPTO:
        raise AssertionError("wrong asset-type")
    if p.portfolio_size != 5000:
        raise AssertionError("wrong size")

    return True
