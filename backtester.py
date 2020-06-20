import getopt
import os
import sys
import uuid

import pygit2

from common import config
from common.tlog import tlog


def get_batch_list():
    pass


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
