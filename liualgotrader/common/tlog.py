import os
from datetime import datetime

from google.cloud import logging

from liualgotrader.common import config

try:
    logger = logging.Client().logger("trader")
except Exception:
    logger = None


def tlog(msg: str) -> None:
    if logger:
        try:
            logger.log_text(f"[{config.env}][{os.getpid()}] {msg}")
        except Exception as e:
            print(f"[Error] exception when trying to log to Stackdriver {e}")
            pass
    print(f"[{os.getpid()}]{datetime.now()}:{msg}", flush=True)
