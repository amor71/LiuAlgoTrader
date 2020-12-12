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
    await trades("89177ae2-a459-4614-a2bc-474f1e0b7c89")
