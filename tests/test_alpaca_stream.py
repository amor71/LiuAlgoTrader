import asyncio
from multiprocessing import Queue

import pytest

from liualgotrader.common.types import QueueMapper, WSEventType
from liualgotrader.data.alpaca import AlpacaStream

alpaca_stream: AlpacaStream
queues: QueueMapper


@pytest.fixture
def event_loop():
    global alpaca_stream
    global queues
    loop = asyncio.get_event_loop()
    queues = QueueMapper()
    alpaca_stream = AlpacaStream(queues)

    yield loop
    loop.close()


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_apple_sec_agg():
    global polygon_stream
    await alpaca_stream.run()
    print("going to subscribe")
    queues["JNUG"] = Queue()
    queues["GLD"] = Queue()
    queues["AAPL"] = Queue()
    status = await alpaca_stream.subscribe(
        ["JNUG", "GLD", "AAPL"], [WSEventType.MIN_AGG]
    )
    print(f"subscribe resut: {status}")
    if not status:
        raise AssertionError(f"Failed in alpaca_stream.subscribe w/ {status}")
    await asyncio.sleep(5 * 60)
    await alpaca_stream.close()

    return True
