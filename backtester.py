import asyncio
import getopt
import os
import pprint
import sys
import traceback

import pygit2

from common import config
from common.database import create_db_connection
from common.decorators import timeit
from common.tlog import tlog
from models.algo_run import AlgoRun


def get_batch_list():
    @timeit
    async def get_batch_list_worker():
        await create_db_connection()
        data = await AlgoRun.get_batches()
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(data)

    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(get_batch_list_worker())
    except KeyboardInterrupt:
        tlog("get_batch_list() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"get_batch_list() - exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()


"""
starting
"""


def show_usage():
    print(f"usage: {sys.argv[0]} -b -v --batch-list --version\n")
    print("-v, --version\t\tDetailed version details")
    print(
        "-b, --batch-list\tDisplay list of trading sessions, list limited to last 30 days"
    )


def show_version(filename: str, version: str) -> None:
    """Display welcome message"""
    print(f"filename:{filename}\ngit version:{version}\n")


if __name__ == "__main__":
    config.build_label = pygit2.Repository("./").describe(
        describe_strategy=pygit2.GIT_DESCRIBE_TAGS
    )
    config.filename = os.path.basename(__file__)

    if len(sys.argv) == 1:
        show_usage()
        sys.exit(0)

    try:
        opts, args = getopt.getopt(
            sys.argv[1:], "vb", ["batch-list", "version"]
        )

        for opt, arg in opts:
            if opt in ["-v", "--version"]:
                show_version(config.filename, config.build_label)
                break
            elif opt in ["--batch-list", "-b"]:
                get_batch_list()
                break

    except getopt.GetoptError as e:
        print(f"Error parsing options:{e}\n")
        show_usage()
        sys.exit(0)

    sys.exit(0)
