import asyncio
import time
from typing import Dict, Optional

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog

if config.trace_enabled:
    from opentelemetry.trace.propagation.tracecontext import \
        TraceContextTextMapPropagator

    from liualgotrader.common.tracer import get_tracer  # type: ignore

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


def trace(carrier: Optional[Dict]):
    def trace_inner(func):
        async def helper(*args, **params):
            if tracer and config.trace_enabled:

                if not bool(carrier):
                    with tracer.start_as_current_span(str(func.__name__)):
                        TraceContextTextMapPropagator().inject(carrier=carrier)
                        params["carrier"] = carrier
                        return await func(*args, **params)
                else:
                    ctx = TraceContextTextMapPropagator().extract(
                        carrier=carrier
                    )
                    with tracer.start_as_current_span(
                        str(func.__name__), context=ctx
                    ):
                        params["carrier"] = carrier
                        return await func(*args, **params)

            return await func(*args, **params)

        return helper

    return trace_inner
