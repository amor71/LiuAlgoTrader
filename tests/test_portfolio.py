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
async def test_exists_negative() -> None:
    result = await Portfolio.exists("1234")
    if result == True:
        raise AssertionError("result should be False")
    print(result)


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_exists_positive() -> None:
    new_id: str = str(uuid.uuid4())
    await Portfolio.save(
        new_id,
        5000,
        10,
        {},
    )
    result = await Portfolio.exists(new_id)
    if result == False:
        raise AssertionError(f"result should be True for {new_id}")

    print(result)


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_balance_positive() -> None:
    new_id: str = str(uuid.uuid4())
    await Portfolio.save(
        new_id,
        5000,
        10,
        {},
    )
    result = await Portfolio.get_portfolio_account_balance(new_id)
    if result != 5000:
        raise AssertionError("result should be 5000")

    print(result)


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_get_external_account_id_positive() -> None:
    new_id: str = str(uuid.uuid4())
    x_id: str = str(uuid.uuid4())
    await Portfolio.save(
        new_id, 5000, 10, {}, AssetType.CRYPTO, x_id, "ALPACA"
    )
    external_account_id, broker = await Portfolio.get_external_account_id(
        new_id
    )
    if external_account_id != x_id or broker != "ALPACA":
        raise AssertionError("failed to load external_account_id details")

    print(external_account_id, broker)


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_get_external_account_id_positive2() -> None:
    new_id: str = str(uuid.uuid4())
    await Portfolio.save(
        new_id,
        5000,
        10,
        {},
    )
    external_account_id, broker = await Portfolio.get_external_account_id(
        new_id
    )
    if external_account_id or broker:
        raise AssertionError("failed to load external_account_id details")

    print(external_account_id, broker)


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_crypto_1() -> None:
    new_id: str = str(uuid.uuid4())
    await Portfolio.save(new_id, 5000, 10, {}, asset_type=AssetType.CRYPTO)
    result = await Portfolio.exists(new_id)
    if result == False:
        raise AssertionError(f"result should be True for {new_id}")

    print(result)


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_crypto_2() -> None:
    new_id: str = str(uuid.uuid4())
    await Portfolio.save(new_id, 5000, 10, {}, asset_type=AssetType.CRYPTO)
    result = await Portfolio.exists(new_id)
    if result == False:
        raise AssertionError(f"result should be True for {new_id}")

    p = await Portfolio.load_by_portfolio_id(new_id)
    print(p)
    if p.asset_type != AssetType.CRYPTO:
        raise AssertionError("wrong asset-type")
    if p.portfolio_size != 5000:
        raise AssertionError("wrong size")
