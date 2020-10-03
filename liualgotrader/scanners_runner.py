import asyncio
import importlib.util
import json
import multiprocessing as mp
import os
from datetime import datetime, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog
from liualgotrader.scanners.base import Scanner
from liualgotrader.scanners.momentum import Momentum

scanner_tasks = []


async def scanner_runner(scanner: Scanner, queue: mp.Queue) -> None:
    try:
        while True:
            symbols = await scanner.run()

            if len(symbols):
                tlog(f"Scanner {scanner.name} picked {len(symbols)} symbols")
                queue.put(
                    json.dumps(
                        [
                            {
                                "symbol": symbol,
                                "target_strategy_name": scanner.target_strategy_name,
                            }
                            for symbol in symbols
                        ]
                    )
                )

            if scanner.recurrence:
                try:
                    await asyncio.sleep(scanner.recurrence.total_seconds())
                    tlog(f"scanner {scanner.name} re-running")
                except asyncio.CancelledError:
                    tlog(
                        f"scanner_runner({scanner.name}) cancelled during sleep, closing scanner task"
                    )
                    break
            else:
                break

    except asyncio.CancelledError:
        tlog(f"scanner_runner() cancelled, closing scanner task {scanner.name}")
    except Exception as e:
        tlog(
            f"[ERROR]Exception in scanner_runner({scanner.name}): exception of type {type(e).__name__} with args {e.args}"
        )
    finally:
        tlog(f"scanner_runner {scanner.name} completed")


async def scanners_runner(scanners_conf: Dict, queue: mp.Queue) -> None:
    data_api = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )

    for scanner_name in scanners_conf:
        if scanner_name == "momentum":
            scanner_details = scanners_conf[scanner_name]
            try:
                recurrence = scanner_details.get("recurrence", None)
                target_strategy_name = scanner_details.get("target_strategy_name", None)
                scanner_object = Momentum(
                    provider=scanner_details["provider"],
                    data_api=data_api,
                    min_last_dv=scanner_details["min_last_dv"],
                    min_share_price=scanner_details["min_share_price"],
                    max_share_price=scanner_details["max_share_price"],
                    min_volume=scanner_details["min_volume"],
                    from_market_open=scanner_details["from_market_open"],
                    today_change_percent=scanner_details["min_gap"],
                    recurrence=timedelta(minutes=recurrence) if recurrence else None,
                    target_strategy_name=target_strategy_name,
                    max_symbols=scanner_details.get(
                        "max_symbols", config.total_tickers
                    ),
                )
                tlog(f"instantiated momentum scanner")
            except KeyError as e:
                tlog(
                    f"Error {e} in processing of scanner configuration {scanner_details}"
                )
                exit(0)
        else:
            tlog(f"custom scanner {scanner_name} selected")
            scanner_details = scanners_conf[scanner_name]
            try:
                spec = importlib.util.spec_from_file_location(
                    "module.name", scanner_details["filename"]
                )
                custom_scanner_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(custom_scanner_module)  # type: ignore
                class_name = scanner_name
                custom_scanner = getattr(custom_scanner_module, class_name)

                if not issubclass(custom_scanner, Scanner):
                    tlog(f"custom scanner must inherit from class {Scanner.__name__}")
                    exit(0)

                scanner_details.pop("filename")
                if "recurrence" not in scanner_details:
                    scanner_object = custom_scanner(
                        data_api=data_api,
                        **scanner_details,
                    )
                else:
                    recurrence = scanner_details.pop("recurrence")
                    scanner_object = custom_scanner(
                        data_api=data_api,
                        recurrence=timedelta(minutes=recurrence),
                        **scanner_details,
                    )

            except Exception as e:
                tlog(
                    f"[Error] scanners_runner.scanners_runner() for {scanner_name}:{e} "
                )

        scanner_tasks.append(asyncio.create_task(scanner_runner(scanner_object, queue)))

    try:
        await asyncio.gather(
            *scanner_tasks,
            return_exceptions=True,
        )

    except asyncio.CancelledError:
        tlog("scanners_runner.scanners_runner() cancelled, closing scanner tasks")

        for task in scanner_tasks:
            tlog(
                f"scanners_runner.scanners_runner()  requesting task {task.get_name()} to cancel"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                tlog("scanners_runner.scanners_runner()  task is cancelled now")

    finally:
        queue.close()
        tlog("scanners_runner.scanners_runner()  done.")


async def teardown_task(tz: DstTzInfo, tasks: List[asyncio.Task]) -> None:
    tlog("scanners_runner.teardown_task() starting")
    dt = datetime.today().astimezone(tz)
    to_market_close: timedelta
    try:
        to_market_close = (
            config.market_close - dt
            if config.market_close > dt
            else timedelta(hours=24) + (config.market_close - dt)
        )
        tlog(
            f"scanners_runner.teardown_task() task waiting for market close: {to_market_close}"
        )
    except Exception as e:
        tlog(
            f"scanners_runner.teardown_task() - exception of type {type(e).__name__} with args {e.args}"
        )
        return

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 5)
        tlog("scanners_runner.teardown_task() closing tasks")

        for task in tasks:
            tlog(
                f"scanners_runner.teardown_task() requesting task {task.get_name()} to cancel"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                tlog("scanners_runner.teardown_task() task is cancelled now")

    except asyncio.CancelledError:
        tlog("scanners_runner.teardown_task() cancelled during sleep")
    finally:
        tlog("scanners_runner.teardown_task() done.")


async def async_main(scanners_conf: Dict, queue: mp.Queue) -> None:
    await create_db_connection(str(config.dsn))

    main_task = asyncio.create_task(
        scanners_runner(scanners_conf, queue),
        name="main_task",
    )

    tear_down = asyncio.create_task(
        teardown_task(
            timezone("America/New_York"),
            [main_task],
        )
    )

    await asyncio.gather(
        main_task,
        tear_down,
        return_exceptions=True,
    )


def main(
    conf_dict: Dict,
    market_open: datetime,
    market_close: datetime,
    scanner_queue: mp.Queue,
) -> None:
    tlog(f"*** scanners_runner.main() starting w pid {os.getpid()} ***")

    config.market_open = market_open
    config.market_close = market_close
    config.bypass_market_schedule = conf_dict.get("bypass_market_schedule", False)
    scanners_conf = conf_dict["scanners"]
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        asyncio.run(async_main(scanners_conf, scanner_queue))
    except KeyboardInterrupt:
        tlog("scanners_runner.main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"scanners_runner.main() - exception of type {type(e).__name__} with args {e.args}"
        )

    tlog("*** scanners_runner.main() completed ***")
