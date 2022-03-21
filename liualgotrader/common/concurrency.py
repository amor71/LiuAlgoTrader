import psutil

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog


def calc_num_consumer_processes() -> int:
    if config.num_consumers > 0:
        return config.num_consumers

    num_cpu = psutil.cpu_count(False)

    if not num_cpu:
        tlog(
            "Can't automatically detect number of CPUs, use fixed configuration"
        )
        return 1

    load_pct: float = psutil.cpu_percent(interval=5)

    tlog(f"Total CPU Load:{load_pct}, num_cpu:{num_cpu}")

    return int(5.0 * (1 - load_pct / 100.0) * num_cpu)
