import asyncio
import importlib.util
import multiprocessing as mp
import os
from datetime import datetime
from typing import Dict, List

import alpaca_trade_api as tradeapi

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.scanners.base import Scanner
from liualgotrader.scanners.momentum import Momentum


async def scanners_runner(scanners_conf: Dict, queue: mp.Queue) -> None:
    data_api = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )

    for scanner in scanners_conf:
        scanner_name = list(scanner.keys())[0]
        if scanner_name == "momentum":
            scanner_details = scanner[scanner_name]
            try:
                print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
                scanner_object = Momentum(
                    provider=scanner_details["provider"],
                    data_api=data_api,
                    min_last_dv=scanner_details["min_last_dv"],
                    min_share_price=scanner_details["min_share_price"],
                    max_share_price=scanner_details["max_share_price"],
                    min_volume=scanner_details["min_volume"],
                    from_market_open=scanner_details["from_market_open"],
                    today_change_percent=scanner_details["min_gap"],
                    recurrence=scanner_details.get("recurrence", False),
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
            print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
            tlog(f"custom scanner {scanner_name} selected")
            scanner_details = scanner[scanner_name]
            try:
                spec = importlib.util.spec_from_file_location(
                    "module.name", scanner_details["filename"]
                )
                custom_scanner_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(custom_scanner_module)  # type: ignore
                class_name = list(scanner.keys())[0]
                custom_scanner = getattr(custom_scanner_module, class_name)

                if not issubclass(custom_scanner, Scanner):
                    tlog(
                        f"custom scanner must inherit from class {Scanner.__name__}"
                    )
                    exit(0)

                if "recurrence" not in scanner_details:
                    scanner_object = custom_scanner(
                        recurrence=False,
                        data_api=data_api,
                        **scanner_details,
                    )
                else:
                    scanner_object = custom_scanner(
                        data_api=data_api, **scanner_details
                    )

            except Exception as e:
                tlog(f"Error {e}")
                exit(0)

        symbols = scanner_object.run()

        for symbol in symbols:
            try:
                queue.put(symbol)

            except Exception as e:
                tlog(
                    f"[ERROR]Exception in scanners_runner(): exception of type {type(e).__name__} with args {e.args}"
                )


def main(
    scanners_conf: Dict,
    market_open: datetime,
    market_close: datetime,
    scanner_queue: mp.Queue,
) -> None:
    tlog(f"*** scanners_runner.main() starting w pid {os.getpid()} ***")
    config.market_open = market_open
    config.market_close = market_close
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        asyncio.run(scanners_runner(scanners_conf, scanner_queue))

    except KeyboardInterrupt:
        tlog("scanners_runner.main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"scanners_runner.main() - exception of type {type(e).__name__} with args {e.args}"
        )

    tlog("*** scanners_runner.main() completed ***")
