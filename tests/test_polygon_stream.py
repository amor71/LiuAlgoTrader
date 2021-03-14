import asyncio
from multiprocessing import Queue

import pytest

from liualgotrader.data.polygon import PolygonStream
from liualgotrader.data.streaming_base import QueueMapper, WSEventType
from liualgotrader.trading.alpaca import AlpacaTrader

queues: QueueMapper
polygon_stream: PolygonStream


@pytest.fixture
def event_loop():
    global polygon_stream
    global queues
    loop = asyncio.get_event_loop()
    queues = QueueMapper()
    polygon_stream = PolygonStream(queues)
    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_apple_sec_agg():
    global polygon_stream
    global queues

    queues["AAPL"] = Queue()
    queues["GLD"] = Queue()
    apple = await polygon_stream.subscribe(
        ["AAPL", "GLD"], [WSEventType.SEC_AGG]
    )
    apple = await polygon_stream.subscribe(
        ["AAPL", "GLD"], [WSEventType.MIN_AGG]
    )
    print(apple)
    await asyncio.sleep(5 * 60)

    print("done")
    await polygon_stream.close()

    return True
