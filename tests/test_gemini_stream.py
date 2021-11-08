import asyncio
import time
from multiprocessing import Queue
from threading import Thread

import pytest

from liualgotrader.common.types import QueueMapper, WSEventType
from liualgotrader.data.gemini import GeminiStream

gemini_stream: GeminiStream
queues: QueueMapper
stop: bool = False


@pytest.fixture
def event_loop():
    global gemini_stream
    global queues
    loop = asyncio.get_event_loop()
    queues = QueueMapper()
    gemini_stream = GeminiStream(queues)

    yield loop
    loop.close()


def listener(q: Queue):
    print("start listen", q)
    while not stop:
        try:
            d = q.get(timeout=2)
            print("got in q:", d)
        except Exception as e:
            print(e, "timeout...")
            time.sleep(1)

    print("end listen")


@pytest.mark.asyncio
@pytest.mark.devtest
async def test_apple_sec_agg():
    global gemini_stream
    global stop
    await gemini_stream.run()
    print("going to subscribe")
    q = Queue()
    queues["BTCUSD"] = q
    running_task = Thread(
        target=listener,
        args=(q,),
    )
    print("start thread")
    running_task.start()
    print("started")
    await asyncio.sleep(2)

    status = await gemini_stream.subscribe(
        ["BTCUSD"], [WSEventType.MIN_AGG, WSEventType.TRADE]
    )
    print(f"subscribe result: {status}")
    if not status:
        raise AssertionError(f"Failed in gemini_stream.subscribe w/ {status}")
    await asyncio.sleep(1 * 60)
    await gemini_stream.close()

    stop = True
    running_task.join()

    return True
