from google.cloud import logging

import config

logger = logging.Client().logger("trader")


def tlog(msg: str) -> None:
    logger.log_text(f"[{config.env}] {msg}")
    print(msg)
