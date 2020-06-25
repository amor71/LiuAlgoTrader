"""
Trading strategy runner
"""
import asyncio
import os
from datetime import datetime, timedelta
from multiprocessing import Queue
from typing import Dict, List

import alpaca_trade_api as tradeapi
from google.cloud import error_reporting
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from common import config
from common.tlog import tlog
from data_stream.finnhub import FinnhubStreaming
from data_stream.streaming_base import StreamingBase
from polygon_producer import trade_run

error_logger = error_reporting.Client()


async def run_finnhub(symbols: List[str], data_ws: StreamingBase) -> None:
    data_channels = []
    for symbol in symbols[:50]:
        symbol_channels = [f"{OP}.{symbol}" for OP in config.WS_DATA_CHANNELS]
        data_channels += symbol_channels

        if data_ws:
            await data_ws.subscribe(symbol, FinnhubStreaming.handler)

    tlog(f"Watching {len(symbols)} symbols using Finnhub websocket service")


async def teardown_task(tz: DstTzInfo, ws: List[StreamingBase] = None) -> None:
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
        if ws:
            tlog("teardown closing web-sockets")
            for w in ws:
                await w.close()

        asyncio.get_running_loop().stop()
    finally:
        tlog("teardown_task() done.")


"""
process main
"""


async def producer_async_main(
    queues: List[Queue], symbols: List[str], queue_id_hash: Dict[str, int]
):

    finnhub_ws = FinnhubStreaming(
        api_key=config.finnhub_api_key,
        queues=queues,
        queue_id_hash=queue_id_hash,
    )
    await finnhub_ws.connect()

    main_task = asyncio.create_task(
        run_finnhub(symbols=symbols, data_ws=finnhub_ws,)
    )

    base_url = (
        config.prod_base_url if config.env == "PROD" else config.paper_base_url
    )
    api_key_id = (
        config.prod_api_key_id
        if config.env == "PROD"
        else config.paper_api_key_id
    )
    api_secret = (
        config.prod_api_secret
        if config.env == "PROD"
        else config.paper_api_secret
    )

    trade_ws = tradeapi.StreamConn(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret,
    )

    trade_updates_task = asyncio.create_task(
        trade_run(ws=trade_ws, queues=queues, queue_id_hash=queue_id_hash)
    )

    tear_down = asyncio.create_task(
        teardown_task(timezone("America/New_York"), [finnhub_ws, trade_ws])
    )

    await asyncio.gather(
        main_task, tear_down, trade_updates_task, return_exceptions=True,
    )


def finnhub_producer_main(
    queues: List[Queue], symbols: List[str], queue_id_hash: Dict[str, int]
) -> None:
    tlog(f"*** finnhub_producer_main() starting w pid {os.getpid()} ***")
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(
            producer_async_main(queues, symbols, queue_id_hash)
        )
        loop.run_forever()
    except KeyboardInterrupt:
        tlog("finnhub_producer_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"finnhub_producer_main() - exception of type {type(e).__name__} with args {e.args}"
        )

    tlog("*** finnhub_producer_main() completed ***")
