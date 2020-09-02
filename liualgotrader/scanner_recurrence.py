import asyncio
import os
from datetime import datetime
from typing import Dict, List

from liualgotrader.common.tlog import tlog


def scanner_recurrence_main(
    symbols: List[str],
    queue_id_hash: Dict[str, int],
    market_close: datetime,
) -> None:
    tlog(f"*** scanner_recurrence_main() starting w pid {os.getpid()} ***")
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        # asyncio.run(producer_async_main(queues, symbols, queue_id_hash))

    except KeyboardInterrupt:
        tlog("scanner_recurrence_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"scanner_recurrence_main() - exception of type {type(e).__name__} with args {e.args}"
        )

    tlog("*** scanner_recurrence_main completed ***")
