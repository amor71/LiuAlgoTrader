import asyncio

import pytest

from liualgotrader.common import config

config.debug_enabled = True

from liualgotrader.common.decorators import trace
from liualgotrader.common.tracer import get_tracer  # type: ignore

tracer = get_tracer()


@pytest.fixture
def event_loop():
    loop = asyncio.get_event_loop()
    yield loop


async def part1(duration=0.025, carrier=None):
    print("part1", duration)
    await asyncio.sleep(duration)
    await trace(carrier)(part2)()


async def part2(duration=0.025, carrier=None):
    print("part2", duration)
    await asyncio.sleep(duration)
    asyncio.create_task(trace(carrier)(part3)(duration=0.075))


async def part3(duration=0.025, carrier=None):
    print("part3", duration)
    await asyncio.sleep(duration)


async def part2_1():
    print("part2_1")
    await asyncio.sleep(0.025)

    await part2_2()


async def part2_2():
    print("part2_2")
    await asyncio.sleep(0.025)

    asyncio.create_task(part2_3())


async def part2_3():
    print("part2_3")
    await asyncio.sleep(0.025)


async def part3_1(carrier=None):
    print("part3_1")
    await asyncio.sleep(0.025)

    await trace(carrier)(part3_2)()


async def part3_2(carrier=None):
    print("part3_2")
    await asyncio.sleep(0.025)

    asyncio.create_task(trace(carrier)(part3_3)())


async def part3_3(carrier=None):
    print("part3_3")
    await asyncio.sleep(0.1)


async def part4_1():
    print("part4_1")
    await asyncio.sleep(0.025)

    asyncio.create_task(part4_2())


async def part4_2():
    print("part4_2")
    await asyncio.sleep(0.025)

    asyncio.create_task(part4_3())


async def part4_3():
    print("part4_3")
    await asyncio.sleep(0.025)


async def part5_1():
    print("part5_1")
    await asyncio.sleep(0.025)

    await part5_2()


async def part5_2():
    print("part5_2", flush=True)
    await asyncio.sleep(0.025)

    asyncio.create_task(part5_3())


async def part5_3():
    print("part5_3", flush=True)
    await asyncio.sleep(0.025)


@pytest.mark.asyncio
async def test_trace_basic():
    print("start test_trace_basic")
    config.trace_enabled = True
    for _ in range(10):
        await trace(carrier={})(part1)()

    await asyncio.sleep(1)
    print("end test_trace_basic")


@pytest.mark.asyncio
async def test_trace_basic_no_trace():
    print("start test_trace_basic_no_trace")
    config.trace_enabled = False
    for _ in range(10):
        await trace(carrier={})(part1)()
    print("end test_trace_basic_no_trace")


@pytest.mark.asyncio
async def test_trace_from_task():
    print("start test_trace_from_task")

    config.trace_enabled = True
    for _ in range(10):
        asyncio.create_task(trace({})(part3_1)())
    await asyncio.sleep(1)
    print("end test_trace_from_task")

    return True
