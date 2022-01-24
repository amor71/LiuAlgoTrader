import os
import sys
import traceback
from datetime import datetime

try:
    from liualgotrader.common.config import gcp_logger

    if gcp_logger:
        from google.cloud import logging

        logger = logging.Client().logger("trader")
    else:
        logger = None
except Exception:
    logger = None


def tlog(msg: str, origin: str = None) -> None:
    try:
        calling_fn = (
            f"[{sys._getframe(1).f_code.co_name}()]" if not origin else origin
        )
    except Exception:
        calling_fn = ""

    if logger:
        try:
            logger.log_text(f"{calling_fn}[{os.getpid()}] {msg}")
        except Exception as e:
            print(f"[Error] exception when trying to log to Stackdriver {e}")
    print(f"{calling_fn}[{os.getpid()}]{datetime.now()}:{msg}", flush=True)


def tlog_exception(origin: str):
    traceback.print_exc()
    exc_info = sys.exc_info()
    lines = traceback.format_exception(*exc_info)
    for line in lines:
        tlog(f"{line}", origin)
    del exc_info
