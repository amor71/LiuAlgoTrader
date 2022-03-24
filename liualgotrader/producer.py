"""
Get Market data from Data Providers and pump to consumers
"""
import asyncio
import inspect
import json
import os
import random
import sys
import traceback
from datetime import datetime
from multiprocessing import Queue
from queue import Empty
from typing import Dict, List

from mnqueues import MNQueue

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog, tlog_exception
from liualgotrader.common.types import QueueMapper, WSEventType
from liualgotrader.data.data_factory import streaming_factory
from liualgotrader.models.tradeplan import TradePlan
from liualgotrader.models.trending_tickers import TrendingTickers
from liualgotrader.trading.trader_factory import trader_factory

last_msg_tstamp: datetime = datetime.now()
symbols: List[str] = []
queue_id_hash: Dict[str, int] = {}
symbol_strategy: Dict = {}


def get_new_symbols_and_queues(
    symbols_details: Dict, queues: List[MNQueue], num_consumer_processes: int
) -> List[str]:
    global symbol_strategy
    global symbols

    new_symbols: List = []
    for symbol_details in symbols_details:
        symbol = symbol_details["symbol"].lower()
        if symbol not in symbols:
            new_symbols.append(symbol)
            symbol_strategy[symbol] = symbol_details["target_strategy_name"]
            streaming_factory().get_instance().queues[symbol] = queues[
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
    at = trader_factory(qm)
    tlog(f"trade_run() starting using {at} trading")
    await at.run()
    tlog("trade_run() completed")


async def dispense_strategies(
    consumer_queues: List[MNQueue], tradeplan_entries: List[TradePlan]
) -> None:
    for tradeplan in tradeplan_entries:
        happy_consumer = consumer_queues[
            random.SystemRandom().randint(0, len(consumer_queues) - 1)
        ]

        payload = {
            "EV": "new_strategy",
            "parameters": tradeplan.parameters,
            "portfolio_id": tradeplan.portfolio_id,
        }

        try:
            happy_consumer.put(payload)
        except Exception as e:
            tlog(
                f"Exception in dispense_strategies: exception of type {type(e).__name__} with args {e.args}"
            )
            if config.debug_enabled:
                tlog_exception(str(e))


async def tradeplan_scanner(
    consumer_queues: List[MNQueue],
) -> None:
    tlog("tradeplan_scanner() task starting ")

    last_scan: datetime = datetime.utcnow()
    while True:
        await asyncio.sleep(5 * 60)

        tlog(
            f"tradeplan_scanner(): check for new execution requests since {last_scan}"
        )
        try:
            new_tradeplan_entries = await TradePlan.get_new_entries(
                since=last_scan
            )
            last_scan = datetime.utcnow()

            if new_tradeplan_entries:
                tlog(
                    f"found {len(new_tradeplan_entries)} new tradeplan entries for execution"
                )
                await dispense_strategies(
                    consumer_queues, new_tradeplan_entries
                )
        except Exception as e:
            tlog(f"[EXCEPTION] tradeplan_scanner() {e}")
            if config.debug_enabled:
                tlog_exception(str(e))

    tlog("tradeplan_scanner() task completed")


async def run(
    queues: List[MNQueue],
    qm: QueueMapper,
) -> None:
    global queue_id_hash

    ps = streaming_factory()(qm)
    await ps.run()
    for symbol in symbols:
        symbol = symbol.lower()
        qm[symbol] = queues[queue_id_hash[symbol]]
    await ps.subscribe(
        symbols, [WSEventType.SEC_AGG, WSEventType.MIN_AGG, WSEventType.TRADE]
    )


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

    # TODO: Support multiple brokers
    at = trader_factory(qm)
    trade_updates_task = await at.run()

    scanner_input_task = asyncio.create_task(
        scanner_input(scanner_queue, queues, num_consumer_processes),
        name="scanner_input",
    )

    tradeplan_scanner_task = asyncio.create_task(
        tradeplan_scanner(queues), name="tradeplan_scanner"
    )

    async_tasks_to_gather = [scanner_input_task, tradeplan_scanner_task]

    if inspect.iscoroutinefunction(trade_updates_task):
        async_tasks_to_gather.append(trade_updates_task)  # type: ignore

    await asyncio.gather(
        *async_tasks_to_gather,
        return_exceptions=True,
    )

    tlog("producer_async_main() completed")


def producer_main(
    unique_id: str,
    queues: List[MNQueue],
    conf_dict: Dict,
    scanner_queue: Queue,
    num_consumer_processes: int,
) -> None:
    tlog(f"*** producer_main() starting w pid {os.getpid()} ***")
    try:
        config.batch_id = unique_id
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
