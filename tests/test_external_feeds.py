import pytest

from liualgotrader.common.market_data import index_data, index_history


@pytest.mark.asyncio
async def test_load_sp500_data() -> bool:
    data = await index_data("SP500")

    return len(data) > 0


@pytest.mark.asyncio
async def test_load_sp500_history() -> bool:
    data = await index_history(index="SP500", days=200)

    return len(data) > 0
