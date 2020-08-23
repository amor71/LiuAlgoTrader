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
        logger.log_text(f"[{config.env}][{os.getpid()}] {msg}")
    print(f"[{os.getpid()}]{datetime.now()}:{msg}")
