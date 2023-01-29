"""off-hours calculations, and data collections"""
import asyncio
import importlib.util
import os
import sys
import traceback
from typing import Dict, List

import pygit2
import toml

from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog, tlog_exception
from liualgotrader.miners.base import Miner

# rom liualgotrader.miners.stock_cluster import StockCluster


def motd(filename: str, version: str) -> None:
    """Display welcome message"""

    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"{filename} {version} starting")
    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")
    tlog(f"DSN: {config.dsn}")
    print("+=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=+")


async def main(conf_dict: Dict):
    task_list: List[asyncio.Task] = []

    await create_db_connection()
    for miner in conf_dict["miners"]:
        try:
            if "filename" in conf_dict["miners"][miner]:
                spec = importlib.util.spec_from_file_location(
                    "module.name", conf_dict["miners"][miner]["filename"]
                )
                if not spec:
                    raise AssertionError(
                        f"could not load module {conf_dict['miners'][miner]['filename']}"
                    )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore
            else:
                module = importlib.import_module(
                    f"liualgotrader.miners.{miner}"
                )
            class_name = f"{miner[0].upper()}{miner[1:]}"
            miner_class = getattr(module, class_name)

            if not issubclass(miner_class, Miner):
                tlog(f"Miner must inherit from class {Miner.__name__}")
                exit(0)

            debug = conf_dict["miners"][miner].get("debug", False)
            miner = miner_class(debug=debug, data=conf_dict["miners"][miner])
            task_list.append(asyncio.create_task(miner.run()))
            await asyncio.gather(*task_list)
        except Exception as e:
            tlog_exception(
                f"[ERROR] miner {miner} resulted in exception:`{e}`"
            )


def main_cli() -> None:
    """
    starting
    """
    try:
        build_label = pygit2.Repository("../").describe(
            describe_strategy=pygit2.GIT_DESCRIBE_TAGS
        )
    except pygit2.GitError:
        import liualgotrader

        build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore
    config.build_label = build_label
    filename = os.path.basename(__file__)
    motd(filename=filename, version=build_label)

    # load configuration
    tlog(
        f"loading configuration file from {os.getcwd()}/{config.miner_configuration_filename}"
    )
    try:
        conf_dict = toml.load(config.miner_configuration_filename)
    except FileNotFoundError:
        tlog(
            f"[ERROR] could not locate market_miner configuration file {config.miner_configuration_filename}"
        )
        sys.exit(0)

    try:
        asyncio.run(main(conf_dict))
    except KeyboardInterrupt:
        tlog("market_miner.main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"market_miner.main() - exception of type {type(e).__name__} with args {e.args}"
        )
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
        del exc_info

    tlog("*** market_miner completed ***")


if __name__ == "__main__":
    main_cli()
