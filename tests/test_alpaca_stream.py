import asyncio
import time
from multiprocessing import Queue
from threading import Thread

import pytest

from liualgotrader.common.types import QueueMapper, WSEventType
from liualgotrader.data.alpaca import AlpacaStream

stop: bool = False


def listener(q: Queue):
    print("start listen", q)
    while not stop:
        try:
            d = q.get(timeout=2)
            print("got in q:", d)
        except Exception as e:
            print(type(e), "timeout...")
            time.sleep(1)

    print("end listen")


@pytest.mark.asyncio
async def test_crypto_stream():
    global stop
    queues = QueueMapper()
    alpaca_stream = AlpacaStream(queues)
    await alpaca_stream.run()

    print("going to subscribe")
    queues["BTC/USD"] = Queue()
    running_task = Thread(
        target=listener,
        args=(queues["BTC/USD"],),
    )
    print("start listen thread")
    running_task.start()
    print("started")

    await asyncio.sleep(2)
    status = await alpaca_stream.subscribe(
        ["BTC/USD"],
        [WSEventType.MIN_AGG, WSEventType.TRADE, WSEventType.QUOTE],
    )
    print(f"subscribe result: {status}")
    if not status:
        raise AssertionError(f"Failed in alpaca_stream.subscribe w/ {status}")
    await asyncio.sleep(1 * 60)
    await alpaca_stream.close()

    tasks = asyncio.all_tasks()
    for t in tasks:
        if not t.done():
            print(t)

    stop = True
    running_task.join()

    return True
