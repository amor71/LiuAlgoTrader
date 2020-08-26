import asyncio
import time

from liualgotrader.common.tlog import tlog


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
