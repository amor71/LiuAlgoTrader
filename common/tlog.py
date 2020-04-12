from google.cloud import logging

from common import config

try:
    logger = logging.Client().logger("trader")
except Exception:
    logger = None


def tlog(msg: str) -> None:
    if logger:
        logger.log_text(f"[{config.env}] {msg}")
    print(msg)
