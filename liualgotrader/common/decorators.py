import asyncio
import time
from typing import Coroutine

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


def retry(retry_times, exception, retry_func):
    def inner_decorator(func):
        async def process(func, *args, **params):
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **params)
            else:
                return func(*args, **params)

        async def helper(*args, **params):
            retry_times = 5
            while retry_times:
                try:
                    return await process(func, *args, **params)
                except exception:
                    await retry_func()
                    asyncio.sleep(1)
                    retry_times -= 1

        return helper

    return inner_decorator
