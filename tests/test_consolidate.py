from datetime import timedelta

import pytest
from hypothesis import example, given, settings
from hypothesis.strategies import text

from liualgotrader.analytics.consolidate import trades


@settings(deadline=None, max_examples=3)  # type: ignore
@given(text())
@pytest.mark.asyncio
@pytest.mark.devtest
async def test_trades(batch_id: str) -> None:
    await trades(batch_id)
