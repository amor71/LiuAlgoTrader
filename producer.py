"""
Trading strategy runner
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from multiprocessing import Queue
from typing import List

import alpaca_trade_api as tradeapi
from alpaca_trade_api.stream2 import StreamConn
from google.cloud import error_reporting
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from common import config
from common.tlog import tlog
from data_stream.alpaca import AlpacaStreaming
from data_stream.streaming_base import StreamingBase

error_logger = error_reporting.Client()


async def run(
    symbols: List[str],
    data_ws: StreamConn,
    data_ws2: StreamingBase,
    queue: Queue,
) -> None:
    data_channels = []
    for symbol in symbols:
        symbol_channels = [f"{OP}.{symbol}" for OP in config.WS_DATA_CHANNELS]
        data_channels += symbol_channels

        # if data_ws2:
        #    await data_ws2.subscribe(symbol, AlpacaStreaming.minutes_handler)

    tlog(f"Watching {len(symbols)} symbols.")

    @data_ws.on(r"T$")
    async def handle_trade_event(conn, channel, data):
        # tlog(f"trade event: {conn} {channel} {data}")
        pass

    @data_ws.on(r"Q$")
    async def handle_quote_event(conn, channel, data):
        # tlog(f"quote event: {conn} {channel} {data}")
        pass

    @data_ws.on(r"A$")
    async def handle_second_bar(conn, channel, data):
        try:
            # print(f"{data.symbol}")
            if (time_diff := datetime.now(tz=timezone("America/New_York")) - data.start) > timedelta(seconds=8):  # type: ignore
                tlog(f"A$ {data.symbol}: data out of sync {time_diff}")
                pass
            else:
                data.__dict__["_raw"]["event"] = "A"
                queue.put(json.dumps(data.__dict__["_raw"]))

        except Exception as e:
            tlog(
                f"Exception in handle_second_bar(): exception of type {type(e).__name__} with args {e.args}"
            )

    @data_ws.on(r"AM$")
    async def handle_minute_bar(conn, channel, data):
        try:
            data.__dict__["_raw"]["event"] = "AM"
            queue.put(json.dumps(data.__dict__["_raw"]))
        except Exception as e:
            tlog(
                f"Exception in handle_minute_bar(): exception of type {type(e).__name__} with args {e.args}"
            )

    await data_ws.subscribe(data_channels)


async def teardown_task(tz: DstTzInfo, ws: List[StreamConn]) -> None:
    tlog("teardown_task() starting")
    dt = datetime.today().astimezone(tz)
    to_market_close = (
        config.market_close - dt
        if config.market_close > dt
        else timedelta(hours=24) + (config.market_close - dt)
    )
    tlog(f"tear-down task waiting for market close: {to_market_close}")
    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 10)
    except asyncio.CancelledError:
        tlog("teardown_task() cancelled during sleep")
    else:
        tlog("teardown closing web-sockets")
        for w in ws:
            await w.close()

        asyncio.get_running_loop().stop()
    finally:
        tlog("teardown_task() done.")


"""
process main
"""


async def producer_async_main(queue: Queue, symbols: List[str]):
    data_ws = tradeapi.StreamConn(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
        data_stream="polygon",
    )
    alpaca_ws = AlpacaStreaming(
        key=config.prod_api_key_id, secret=config.prod_api_secret
    )
    await alpaca_ws.connect()

    main_task = asyncio.create_task(
        run(symbols=symbols, data_ws=data_ws, data_ws2=alpaca_ws, queue=queue,)
    )

    tear_down = asyncio.create_task(
        teardown_task(timezone("America/New_York"), [data_ws])
    )

    await asyncio.gather(
        main_task, tear_down, return_exceptions=True,
    )


def producer_main(queue: Queue, symbols: List[str]) -> None:
    tlog(f"*** producer_main() starting w pid {os.getpid()} ***")
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(producer_async_main(queue, symbols))
        loop.run_forever()
    except KeyboardInterrupt:
        tlog("producer_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"producer_main() - exception of type {type(e).__name__} with args {e.args}"
        )

    tlog("*** producer_main() completed ***")
