import asyncio
import uuid

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.models.keystore import KeyStore

strategy_name: str = str(uuid.uuid4())
context: str = str(uuid.uuid4())


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_load_empty() -> bool:
    data = await KeyStore.load("some_lie")

    if data:
        raise AssertionError(f"empty field must be None and not {data}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_insert() -> bool:
    await KeyStore.save("k1", "v1")
    data = await KeyStore.load("k1")

    if data != "v1":
        raise AssertionError(f"failed to insert and load key")

    print(f"test_insert: {strategy_name} k1={data}")
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_update() -> bool:
    await KeyStore.save("k2", "v21")
    data = await KeyStore.load("k2")

    if data != "v21":
        raise AssertionError(f"failed to insert and load key")

    await KeyStore.save("k2", "v22")
    data = await KeyStore.load("k2")
    if data != "v22":
        raise AssertionError(f"failed to update and load key")

    print(f"test_update: {strategy_name} k2={data}")

    return True
