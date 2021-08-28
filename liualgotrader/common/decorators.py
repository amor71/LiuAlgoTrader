import asyncio
import time
from typing import Coroutine

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog

if config.trace_enabled:
    from liualgotrader.common.tracer import get_tracer

    tracer = get_tracer()
else:
    tracer = None


def timeit(func):
    async def process(func, *args, **params):
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **params)
        else:
            return func(*args, **params)

    async def helper(*args, **params):
        tlog(f"{func.__name__} started")
        start = time.time()
        result = await process(func, *args, **params)
        tlog(f"{func.__name__} >>> {round(time.time() - start, 3)} seconds")
        return result

    return helper


def trace(func):
    async def process(func, *args, **params):
        return await func(*args, **params)

    async def helper(*args, **params):
        loop = asyncio.get_event_loop()
        if tracer:
            with tracer.start_as_current_span(
                str(func.__name__)
            ) as current_span:
                result = await process(func, *args, **params)
        else:
            result = await process(func, *args, **params)

        return result

    return helper
