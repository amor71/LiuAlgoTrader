"""
Get Market data from Polygon and pump to consumers
"""
import asyncio
import json
import os
import random
import sys
import traceback
from datetime import datetime, timedelta
from multiprocessing import Queue
from queue import Empty, Full
from typing import Dict, List

import alpaca_trade_api as tradeapi
from alpaca_trade_api.stream2 import StreamConn, polygon
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from liualgotrader.common import config
from liualgotrader.common.data_loader import DataLoader
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import WSEventType
from liualgotrader.data.polygon import PolygonStream
from liualgotrader.data.streaming_base import QueueMapper
from liualgotrader.models.trending_tickers import TrendingTickers

last_msg_tstamp: datetime = datetime.now()
symbols: List[str]
data_channels: List = []
queue_id_hash: Dict[str, int]
symbol_strategy: Dict = {}


async def scanner_input(
    scanner_queue: Queue,
    queues: List[Queue],
    num_consumer_processes: int,
) -> None:
    tlog("scanner_input() task starting ")
    global data_channels
    global queue_id_hash
    global symbol_strategy
    global symbols

    while True:
        try:
            symbols_details = scanner_queue.get(timeout=1)
            if symbols_details:
                symbols_details = json.loads(symbols_details)
                new_symbols: List = []
                new_channels: List = []
                for symbol_details in symbols_details:
                    if symbol_details["symbol"] not in symbols:
                        new_symbols.append(symbol_details["symbol"])
                        symbol_strategy[
                            symbol_details["symbol"]
                        ] = symbol_details["target_strategy_name"]
                        PolygonStream.get_instance().queues[
                            symbol_details["symbol"]
                        ] = queues[
                            random.SystemRandom().randint(
                                0, num_consumer_processes - 1
                            )
                        ]

                if len(new_symbols):
                    await PolygonStream.get_instance().subscribe(
                        new_symbols, [WSEventType.SEC_AGG, WSEventType.MIN_AGG]
                    )
                    symbols += new_symbols
                    data_channels += new_channels

                    trending_db = TrendingTickers(config.batch_id)
                    await trending_db.save(new_symbols)

                    tlog(
                        f"added {len(new_symbols)}:{new_symbols} TOTAL: {len(symbols)}"
                    )
                    await asyncio.sleep(1)

        except Empty:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            tlog("scanner_input() task task cancelled ")
            break
        except Exception as e:
            tlog(
                f"Exception in scanner_input(): exception of type {type(e).__name__} with args {e.args}"
            )
            exc_info = sys.exc_info()
            lines = traceback.format_exception(*exc_info)
            for line in lines:
                tlog(f"error: {line}")
            traceback.print_exception(*exc_info)
            del exc_info

    tlog("scanner_input() task completed")


async def trade_run(
    ws: StreamConn,
    queues: List[Queue],
) -> None:

    tlog("trade_run() starting using Alpaca trading ")

    @ws.on(r"trade_update")
    async def handle_trade_update(conn, channel, data):
        global queue_id_hash
        try:
            # tlog(f"producer TRADE UPDATE event: {data.__dict__}")
            symbol = data.__dict__["_raw"]["order"]["symbol"]
            if qid := queue_id_hash.get(symbol, None):
                data.__dict__["_raw"]["EV"] = "trade_update"
                data.__dict__["_raw"]["symbol"] = symbol
                queues[qid].put(data.__dict__["_raw"])

        except Exception as e:
            tlog(
                f"[ERROR]Exception in handle_trade_update(): exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()

    await ws.subscribe(["trade_updates"])
    tlog("trade_run() completed")


async def run(
    queues: List[Queue],
) -> None:
    global data_channels
    global queue_id_hash

    qm = QueueMapper()
    ps = PolygonStream(qm)
    for symbol in symbols:
        qm[symbol] = queues[queue_id_hash[symbol]]
    await ps.subscribe(symbols, [WSEventType.SEC_AGG, WSEventType.MIN_AGG])


async def teardown_task(
    tz: DstTzInfo, ws: List[StreamConn], tasks: List[asyncio.Task]
) -> None:
    tlog("poylgon_producer teardown_task() starting")
    if not config.market_close:
        tlog(
            "we're probably in market schedule by-pass mode, exiting poylgon_producer tear-down task"
        )
        return

    dt = datetime.today().astimezone(tz)
    to_market_close: timedelta
    try:
        to_market_close = (
            config.market_close - dt
            if config.market_close > dt
            else timedelta(hours=24) + (config.market_close - dt)
        )
        tlog(
            f"poylgon_producer tear-down task waiting for market close: {to_market_close}"
        )
    except Exception as e:
        tlog(
            f"poylgon_producer - exception of type {type(e).__name__} with args {e.args}"
        )
        return

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 5)

        tlog("closing PolygonStream")
        await PolygonStream.close()

        tlog("poylgon_producer teardown closing web-sockets")
        for w in ws:
            await w.close(False)

        tlog("poylgon_producer teardown closing tasks")

        for task in tasks:
            tlog(
                f"teardown_task(): requesting task {task.get_name()} to cancel"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                tlog("teardown_task(): task is cancelled now")

        # asyncio.get_running_loop().stop()

    except asyncio.CancelledError:
        tlog("teardown_task() cancelled during sleep")

    finally:
        tlog("teardown_task() done.")


"""
process main
"""


async def producer_async_main(
    queues: List[Queue],
    scanner_queue: Queue,
    num_consumer_processes: int,
):
    await create_db_connection(str(config.dsn))

    await run(queues=queues)

    trade_ws = tradeapi.StreamConn(
        base_url=config.alpaca_base_url,
        key_id=config.alpaca_api_key,
        secret_key=config.alpaca_api_secret,
    )

    trade_updates_task = asyncio.create_task(
        trade_run(ws=trade_ws, queues=queues),
        name="trade_updates_task",
    )

    scanner_input_task = asyncio.create_task(
        scanner_input(scanner_queue, queues, num_consumer_processes),
        name="scanner_input",
    )
    tear_down = asyncio.create_task(
        teardown_task(
            timezone("America/New_York"),
            [trade_ws],
            [scanner_input_task],
        )
    )

    await asyncio.gather(
        trade_updates_task,
        scanner_input_task,
        tear_down,
        return_exceptions=True,
    )

    tlog("producer_async_main() completed")


def polygon_producer_main(
    unique_id: str,
    queues: List[Queue],
    current_symbols: List[str],
    current_queue_id_hash: Dict[str, int],
    market_close: datetime,
    conf_dict: Dict,
    scanner_queue: Queue,
    num_consumer_processes: int,
) -> None:
    tlog(f"*** polygon_producer_main() starting w pid {os.getpid()} ***")
    try:
        config.market_close = market_close
        config.batch_id = unique_id
        events = conf_dict.get("events", None)

        if not events:
            config.WS_DATA_CHANNELS = ["A", "AM", "T", "Q"]
        else:
            config.WS_DATA_CHANNELS = []

            if "second" in events:
                config.WS_DATA_CHANNELS.append("AM")
            if "minute" in events:
                config.WS_DATA_CHANNELS.append("A")
            if "trade" in events:
                config.WS_DATA_CHANNELS.append("T")
            if "quote" in events:
                config.WS_DATA_CHANNELS.append("Q")

        tlog(
            f"polygon_producer_main(): listening for events {config.WS_DATA_CHANNELS}"
        )
        global symbols
        global queue_id_hash

        symbols = current_symbols
        queue_id_hash = current_queue_id_hash
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        asyncio.run(
            producer_async_main(queues, scanner_queue, num_consumer_processes)
        )

    except KeyboardInterrupt:
        tlog("polygon_producer_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"polygon_producer_main() - exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()

    tlog("*** polygon_producer_main() completed ***")
