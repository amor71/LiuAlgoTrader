import asyncio

import pytest

from liualgotrader.common.database import create_db_connection
from liualgotrader.common.market_data import (get_industries_tickers,
                                              get_market_industries,
                                              get_market_sectors,
                                              get_sectors_tickers)


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    loop.run_until_complete(create_db_connection())
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_market_industries():
    industry_list = await get_market_industries()

    print(industry_list)

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_market_sectors():
    sector_list = await get_market_sectors()
    print(sector_list)

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_market_sectors_symbols():
    sector_list = await get_market_sectors()

    l = await get_sectors_tickers(sector_list)
    print(f"sectors_tickers {l}")

    return True


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_get_market_industries_symbols():
    industries_list = await get_market_industries()
    l = await get_industries_tickers(industries_list)
    print(l)

    return True
