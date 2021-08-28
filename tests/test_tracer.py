import asyncio
import time

import pytest

from liualgotrader.common import config

config.debug_enabled = True

from liualgotrader.common.decorators import trace


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


@trace
async def part1():
    print("part1")
    await asyncio.sleep(0.025)

    await part2()


@trace
async def part2():
    print("part2")
    await asyncio.sleep(0.025)

    asyncio.create_task(part3())


@trace
async def part3():
    print("part3")
    await asyncio.sleep(0.025)


@trace
async def part2_1():
    print("part2_1")
    await asyncio.sleep(0.025)

    await part2_2()


@trace
async def part2_2():
    print("part2_2")
    await asyncio.sleep(0.025)

    asyncio.create_task(part2_3())


@trace
async def part2_3():
    print("part2_3")
    await asyncio.sleep(0.025)


@trace
async def part3_1():
    print("part3_1")
    await asyncio.sleep(0.025)

    await part3_2()


@trace
async def part3_2():
    print("part3_2")
    await asyncio.sleep(0.025)

    asyncio.create_task(part3_3())


@trace
async def part3_3():
    print("part3_3")
    await asyncio.sleep(0.025)


@trace
async def part4_1():
    print("part4_1")
    await asyncio.sleep(0.025)

    asyncio.create_task(part4_2())


@trace
async def part4_2():
    print("part4_2")
    await asyncio.sleep(0.025)

    asyncio.create_task(part4_3())


@trace
async def part4_3():
    print("part4_3")
    await asyncio.sleep(0.025)


async def part5_1():
    print("part5_1")
    await asyncio.sleep(0.025)

    await part5_2()


@trace
async def part5_2():
    print("part5_2", flush=True)
    await asyncio.sleep(0.025)

    asyncio.create_task(part5_3())


@trace
async def part5_3():
    print("part5_3", flush=True)
    await asyncio.sleep(0.025)


@pytest.mark.asyncio
async def test_trace_basic():
    print("start test_trace_basic")
    for _ in range(10):
        await part1()
    print("end test_trace_basic")


@pytest.mark.asyncio
async def test_trace_parallel():
    print("start test_trace_parallel")
    for _ in range(10):
        await part1()
        await part2_1()
    print("end test_trace_parallel")


@pytest.mark.asyncio
async def test_trace_from_task():
    print("start test_trace_from_task")
    for _ in range(10):
        asyncio.create_task(part3_1())
    await asyncio.sleep(0.1)
    print("end test_trace_from_task")


@pytest.mark.asyncio
async def test_trace_from_task_2():
    print("start test_trace_from_task_2")
    for _ in range(10):
        asyncio.create_task(part4_1())
    await asyncio.sleep(0.1)
    print("end test_trace_from_task_2")


@pytest.mark.asyncio
async def test_trace_from_task_3():
    print("start test_trace_from_task_3")
    for _ in range(10):
        asyncio.create_task(part5_1())

    await asyncio.sleep(0.1)
    print("end test_trace_from_task_3")
