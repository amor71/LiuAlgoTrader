import os
import sys
from datetime import datetime

try:
    from google.cloud import logging

    logger = logging.Client().logger("trader")
except Exception:
    logger = None


def tlog(msg: str) -> None:
    try:
        calling_fn = f"[{sys._getframe(1).f_code.co_name}()]"
    except Exception:
        calling_fn = ""

    if logger:
        try:
            logger.log_text(f"{calling_fn}[{os.getpid()}] {msg}")
        except Exception as e:
            print(f"[Error] exception when trying to log to Stackdriver {e}")
    print(f"{calling_fn}[{os.getpid()}]{datetime.now()}:{msg}", flush=True)
