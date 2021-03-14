import asyncio

import pytest

from liualgotrader.common.types import WSEventType
from liualgotrader.data.alpaca import AlpacaStream, QueueMapper

polygon_stream: AlpacaStream


@pytest.fixture
def event_loop():
    global polygon_stream
    loop = asyncio.get_event_loop()
    polygon_stream = AlpacaStream(QueueMapper())
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_apple_sec_agg():
    global polygon_stream
    apple = await polygon_stream.subscribe(["AAPL"], [WSEventType.SEC_AGG])
    print(apple)
    await asyncio.sleep(5 * 60)

    print("done")
    await polygon_stream.close()

    return True
