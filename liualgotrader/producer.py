"""
Get Market data from Data Providers and pump to consumers
"""
import asyncio
import json
import os
import random
import sys
import traceback
from datetime import datetime, timedelta
from multiprocessing import Queue
from queue import Empty
from typing import Dict, List, Optional

from mnqueues import MNQueue

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper, WSEventType
from liualgotrader.data.data_factory import streaming_factory
from liualgotrader.models.trending_tickers import TrendingTickers
from liualgotrader.trading.alpaca import AlpacaTrader
from liualgotrader.trading.trader_factory import trader_factory

last_msg_tstamp: datetime = datetime.now()
symbols: List[str]
queue_id_hash: Dict[str, int]
symbol_strategy: Dict = {}


def get_new_symbols_and_queues(
    symbols_details: Dict, queues: List[MNQueue], num_consumer_processes: int
) -> List[str]:
    global symbol_strategy

    new_symbols: List = []
    for symbol_details in symbols_details:
        if symbol_details["symbol"] not in symbols:
            new_symbols.append(symbol_details["symbol"])
            symbol_strategy[symbol_details["symbol"]] = symbol_details[
                "target_strategy_name"
            ]
            streaming_factory().get_instance().queues[
                symbol_details["symbol"]
            ] = queues[
                random.SystemRandom().randint(0, num_consumer_processes - 1)
            ]

    return new_symbols


async def subscribe_new_symbols(new_symbols: List[str]):
    await streaming_factory().get_instance().subscribe(
        new_symbols,
        [
            WSEventType.SEC_AGG,
            WSEventType.MIN_AGG,
            WSEventType.TRADE,
        ],
    )


async def scanners_iteration(
    scanner_queue: Queue,
    queues: List[MNQueue],
    num_consumer_processes: int,
):
    global symbols
    symbols_details = scanner_queue.get(timeout=1)
    if len(
        new_symbols := get_new_symbols_and_queues(
            symbols_details=json.loads(symbols_details),
            queues=queues,
            num_consumer_processes=num_consumer_processes,
        )
    ):
        await subscribe_new_symbols(new_symbols)
        trending_db = TrendingTickers(config.batch_id)
        await trending_db.save(new_symbols)
        symbols += new_symbols
        tlog(
            f"added {len(new_symbols)}:{new_symbols[:20]}..{new_symbols[-20:]} TOTAL: {len(symbols)}"
        )
        await asyncio.sleep(1)


async def scanner_input(
    scanner_queue: Queue,
    queues: List[MNQueue],
    num_consumer_processes: int,
) -> None:
    tlog("scanner_input() task starting ")

    while True:
        try:
            await scanners_iteration(
                scanner_queue=scanner_queue,
                queues=queues,
                num_consumer_processes=num_consumer_processes,
            )
        except Empty:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            tlog("scanner_input() task task cancelled ")
            break
        except Exception as e:
            tlog(
                f"Exception in scanner_input(): exception of type {type(e).__name__} with args {e.args}"
            )
            if config.debug_enabled:
                exc_info = sys.exc_info()
                lines = traceback.format_exception(*exc_info)
                for line in lines:
                    tlog(f"error: {line}")
                traceback.print_exception(*exc_info)
                del exc_info

    tlog("scanner_input() task completed")


async def trade_run(qm: QueueMapper) -> None:
    tlog("trade_run() starting using Alpaca trading ")
    at = AlpacaTrader(qm)
    await at.run()
    tlog("trade_run() completed")


async def run(
    queues: List[MNQueue],
    qm: QueueMapper,
) -> None:
    global queue_id_hash

    ps = streaming_factory()(qm)
    await ps.run()
    for symbol in symbols:
        qm[symbol] = queues[queue_id_hash[symbol]]
    await ps.subscribe(
        symbols, [WSEventType.SEC_AGG, WSEventType.MIN_AGG, WSEventType.TRADE]
    )


async def teardown_task(
    to_market_close: Optional[timedelta], tasks: List[asyncio.Task]
) -> None:
    if not to_market_close:
        return
    tlog("producer teardown_task() starting")
    if not config.market_close:
        tlog(
            "we're probably in market schedule by-pass mode, exiting poylgon_producer tear-down task"
        )
        return

    tlog(
        f"producer tear-down task waiting for market close: {to_market_close}"
    )
    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 5)

        tlog("closing Stream")
        await streaming_factory().get_instance().close()
        tlog("producer teardown closed streaming web-sockets")
        await trader_factory().get_instance().close()
        tlog("producer teardown closed trading web-sockets")

        tlog("producer teardown closing tasks")
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

    except Exception as e:
        tlog(f"[ERROR] Exception {e}")
        if config.debug_enabled:
            traceback.print_exc()

    finally:
        tlog("teardown_task() done.")


"""
process main
"""


async def producer_async_main(
    queues: List[MNQueue],
    scanner_queue: Queue,
    num_consumer_processes: int,
):
    await create_db_connection(str(config.dsn))
    qm = QueueMapper(queue_list=queues)
    await run(queues=queues, qm=qm)

    at = AlpacaTrader(qm)

    if not at.get_time_market_close():
        return
    trade_updates_task = await at.run()

    scanner_input_task = asyncio.create_task(
        scanner_input(scanner_queue, queues, num_consumer_processes),
        name="scanner_input",
    )
    tear_down = asyncio.create_task(
        teardown_task(
            at.get_time_market_close(),
            [scanner_input_task, trade_updates_task],
        )
    )

    await asyncio.gather(
        trade_updates_task,
        scanner_input_task,
        tear_down,
        return_exceptions=True,
    )

    tlog("producer_async_main() completed")


def producer_main(
    unique_id: str,
    queues: List[MNQueue],
    current_symbols: List[str],
    current_queue_id_hash: Dict[str, int],
    market_close: datetime,
    conf_dict: Dict,
    scanner_queue: Queue,
    num_consumer_processes: int,
) -> None:
    tlog(f"*** producer_main() starting w pid {os.getpid()} ***")
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
            f"producer_main(): listening for events {config.WS_DATA_CHANNELS}"
        )
        global symbols
        global queue_id_hash

        symbols = current_symbols
        queue_id_hash = current_queue_id_hash
        asyncio.run(
            producer_async_main(queues, scanner_queue, num_consumer_processes)
        )

    except KeyboardInterrupt:
        tlog("producer_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"producer_main() - exception of type {type(e).__name__} with args {e.args}"
        )
        if config.debug_enabled:
            traceback.print_exc()

    tlog("*** producer_main() completed ***")
