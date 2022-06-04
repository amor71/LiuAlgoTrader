import asyncio
import uuid

import pandas as pd
import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.common.types import AssetType
from liualgotrader.models.portfolio import Portfolio


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
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
async def test_balance_positive() -> bool:
    id: str = str(uuid.uuid4())
    await Portfolio.save(
        id,
        5000,
        10,
        {},
    )
    result = await Portfolio.get_portfolio_account_balance(id)
    if result != 5000:
        raise AssertionError("result should be 5000")

    print(result)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_get_external_account_id_positive() -> bool:
    id: str = str(uuid.uuid4())
    x_id: str = str(uuid.uuid4())
    await Portfolio.save(id, 5000, 10, {}, AssetType.CRYPTO, x_id, "ALPACA")
    external_account_id, broker = await Portfolio.get_external_account_id(id)
    if external_account_id != x_id or broker != "ALPACA":
        raise AssertionError("failed to load external_account_id details")

    print(external_account_id, broker)
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_get_external_account_id_positive2() -> bool:
    id: str = str(uuid.uuid4())
    x_id: str = str(uuid.uuid4())
    await Portfolio.save(
        id,
        5000,
        10,
        {},
    )
    external_account_id, broker = await Portfolio.get_external_account_id(id)
    if external_account_id or broker:
        raise AssertionError("failed to load external_account_id details")

    print(external_account_id, broker)
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
