import asyncio

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.models.accounts import Accounts


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_create() -> bool:
    account_id = await Accounts.create(
        balance=1000.0,
        allow_negative=True,
        credit_line=2000.0,
    )
    print(f"new account_id:{account_id}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_negative_create() -> bool:
    try:
        await Accounts.create(
            balance=1000.0,
            allow_negative=True,
        )
    except Exception as e:
        print(e)

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_balance() -> bool:
    balance = 1234.0
    account_id = await Accounts.create(
        balance=balance,
        allow_negative=True,
        credit_line=2000.0,
    )
    print(f"new account_id:{account_id}")
    if balance != await Accounts.get_balance(account_id):
        raise AssertionError("get_balance() did not return the expect value")
    print(f"balance {balance}")
    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_add_transaction() -> bool:
    balance = 1234.0
    account_id = await Accounts.create(
        balance=balance,
        allow_negative=True,
        credit_line=2000.0,
    )
    amount = 1000.0
    await Accounts.add_transaction(account_id, amount)
    if balance + amount != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_add_transaction(): get_balance() did not return the expect value"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_add_transaction2() -> bool:
    balance = 1234.0
    account_id = await Accounts.create(
        balance=balance,
        allow_negative=True,
        credit_line=2000.0,
    )
    amount = 1000.0
    await Accounts.add_transaction(account_id, amount)
    await Accounts.add_transaction(account_id, -amount)
    if balance != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_add_transaction(): get_balance() did not return the expect value"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_add_transaction3() -> bool:
    balance = 1234.0
    account_id = await Accounts.create(
        balance=balance,
        allow_negative=False,
    )
    amount = 1000.0
    await Accounts.add_transaction(account_id, amount)
    await Accounts.add_transaction(account_id, -amount)
    if balance != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_add_transaction3(): get_balance() did not return the expect value"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_negative_add_transaction() -> bool:
    balance = 1234.0
    account_id = await Accounts.create(
        balance=balance,
        allow_negative=False,
    )
    amount = 1000.0
    await Accounts.add_transaction(account_id, amount)
    await Accounts.add_transaction(account_id, -amount)
    try:
        await Accounts.add_transaction(account_id, -10000.0)
    except Exception as e:
        print(e)
    if balance != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_negative_add_transaction(): get_balance() did not return the expect value"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_add_transaction5() -> bool:
    balance = 100.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=5000.0
    )
    amount = 1000.0
    await Accounts.add_transaction(account_id, -amount)
    if balance - amount != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_add_transaction5(): get_balance() did not return the expect value"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_negative_add_transaction2() -> bool:
    balance = 100.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=5000.0
    )
    amount = 10000.0
    try:
        await Accounts.add_transaction(account_id, -amount)
    except Exception as e:
        print(e)

    if balance != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_add_transaction5(): get_balance() did not return the expect value"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_clear_balance() -> bool:
    print("test_clear_balance")
    balance = 1234.0
    account_id = await Accounts.create(
        balance=balance,
        allow_negative=True,
        credit_line=2000.0,
    )
    print(f"new account_id:{account_id}")
    if balance != await Accounts.get_balance(account_id):
        raise AssertionError("get_balance() did not return the expect value")

    print(f"balance {balance}")

    await Accounts.clear_balance(account_id, 0)
    if await Accounts.get_balance(account_id) != 0.0:
        raise AssertionError("clear balance failed")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_clear_transactions() -> bool:
    print("test_clear_transactions")
    balance = 100.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=5000.0
    )
    amount = 1000.0
    await Accounts.add_transaction(account_id, -amount)
    if balance - amount != await Accounts.get_balance(account_id):
        raise AssertionError(
            "test_clear_transactions(): get_balance() did not return the expect value"
        )

    await Accounts.clear_account_transactions(account_id)
    _df = await Accounts.get_transactions(account_id)
    if not _df.empty:
        raise AssertionError(
            "test_clear_transactions(): failed to clear account_transactions"
        )

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_check_if_enough_balance_positive_1() -> bool:
    print("test_check_if_enough_balance_positive_1")

    balance = 1000.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=False, credit_line=0.0
    )

    if await Accounts.check_if_enough_balance_to_withdraw(account_id, 500.0):
        return True
    else:
        raise AssertionError(
            "test_check_if_enough_balance_positive_1(): should have had enough balance"
        )


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_check_if_enough_balance_positive_2() -> bool:
    print("test_check_if_enough_balance_positive_2")

    balance = 1000.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=500.0
    )

    if not await Accounts.check_if_enough_balance_to_withdraw(
        account_id, 2000.0
    ):
        return True
    else:
        raise AssertionError(
            "test_check_if_enough_balance_positive_2(): should not have had enough balance"
        )


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_check_if_enough_balance_positive_3() -> bool:
    print("test_check_if_enough_balance_positive_3")

    balance = 1000.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=500.0
    )
    await Accounts.add_transaction(account_id, -1100)

    if await Accounts.check_if_enough_balance_to_withdraw(account_id, 200.0):
        return True
    else:
        raise AssertionError(
            "test_check_if_enough_balance_positive_3(): should  have had enough balance"
        )


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_check_if_enough_balance_positive_4() -> bool:
    print("test_check_if_enough_balance_positive_4")

    balance = 1000.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=500.0
    )
    await Accounts.add_transaction(account_id, -1100)

    if not await Accounts.check_if_enough_balance_to_withdraw(
        account_id, 600.0
    ):
        return True
    else:
        raise AssertionError(
            "test_check_if_enough_balance_positive_4(): should not have had enough balance"
        )


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_check_if_enough_balance_negative_1() -> bool:
    print("test_check_if_enough_balance_negative_1")

    balance = 1000.0
    account_id = await Accounts.create(
        balance=balance, allow_negative=True, credit_line=500.0
    )
    try:
        not await Accounts.check_if_enough_balance_to_withdraw(
            account_id, -600.0
        )
    except AssertionError:
        return True

    raise AssertionError(
        "test_check_if_enough_balance_negative_1(): should have raise exception"
    )
