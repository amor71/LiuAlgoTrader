import copy
import multiprocessing as mp
import os
import sys
import uuid
from multiprocessing import Queue
from typing import List

import pygit2
import toml
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.concurrency import calc_num_consumer_processes
from liualgotrader.common.tlog import tlog
from liualgotrader.consumer import consumer_main
from liualgotrader.producer import producer_main
from liualgotrader.scanners_runner import main


def motd(filename: str, version: str, unique_id: str) -> None:
    """Display welcome message"""

    tlog("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    tlog("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    tlog(f"{filename} {version} starting")
    tlog(f"unique id: {unique_id}")
    tlog("----------------------------------------------------------")
    tlog("----------------------------------------------------------")


def main_cli():
    config.filename = os.path.basename(__file__)
    mp.set_start_method("spawn")

    try:
        config.build_label = pygit2.Repository("../").describe(
            describe_strategy=pygit2.GIT_DESCRIBE_TAGS
        )
    except pygit2.GitError:
        import liualgotrader

        config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore

    uid = str(uuid.uuid4())
    motd(filename=config.filename, version=config.build_label, unique_id=uid)

    # load configuration
    folder = (
        config.tradeplan_folder
        if config.tradeplan_folder[-1] == "/"
        else f"{config.tradeplan_folder}/"
    )
    fname = f"{folder}{config.configuration_filename}"
    try:
        conf_dict = copy.deepcopy(toml.load(fname))
        print(conf_dict)
        tlog(f"loaded configuration file from {fname}")
    except FileNotFoundError:
        tlog(f"[ERROR] could not locate tradeplan file {fname}")
        sys.exit(0)

    # Consumers first
    num_consumer_processes = calc_num_consumer_processes()
    tlog(f"Starting {num_consumer_processes} consumer processes")
    queues: List[Queue] = [Queue() for _ in range(num_consumer_processes)]
    consumers = [
        mp.Process(
            target=consumer_main,
            args=(queues[i], uid, conf_dict),
        )
        for i in range(num_consumer_processes)
    ]
    for p in consumers:
        # p.daemon = True
        p.start()

    scanner_queue: mp.Queue = mp.Queue()
    producer = mp.Process(
        target=producer_main,
        args=(
            uid,
            queues,
            conf_dict,
            scanner_queue,
            num_consumer_processes,
        ),
    )
    producer.start()

    scanner = None
    if "scanners" in conf_dict:
        tlog("Starting scanners process")
        scanner = mp.Process(
            target=main,
            args=(
                conf_dict,
                scanner_queue,
            ),
        )
        scanner.start()

    # wait for completion and hope everyone plays nicely
    try:
        producer.join()
        if scanner:
            scanner.join()

        for p in consumers:
            p.join()

    except KeyboardInterrupt:
        producer.kill()

        if scanner:
            scanner.terminate()

        for p in consumers:
            p.terminate()

    sys.exit(0)
