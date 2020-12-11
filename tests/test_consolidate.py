import pytest
from hypothesis import example, given, settings
from hypothesis.strategies import text

from liualgotrader.analytics.consolidate import trades


@settings(deadline=None, max_examples=5)  # type: ignore
@given(text())
@pytest.mark.asyncio
async def test_trades(batch_id: str) -> None:
    await trades(batch_id)


@pytest.mark.asyncio
async def test_trades_specific_batch() -> None:
    await trades("7011c385-9920-48f5-8c52-b209c7ba619a")
