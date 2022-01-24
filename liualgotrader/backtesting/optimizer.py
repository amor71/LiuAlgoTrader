import asyncio
import traceback
import uuid
from datetime import date
from typing import Dict

import liualgotrader
from liualgotrader import enhanced_backtest
from liualgotrader.common import config
from liualgotrader.common.hyperparameter import Hyperparameters
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import AssetType, TimeScale
from liualgotrader.models.optimizer import OptimizerRun


async def save_optimizer_session(
    optimizer_session_id: str, batch_id: str, hypers: Hyperparameters
):
    await OptimizerRun.save(optimizer_session_id, batch_id, str(hypers))


def backtest_iteration(
    optimizer_session_id: str,
    start_date: date,
    end_date: date,
    conf_dict: Dict,
    hypers: Hyperparameters,
):
    tlog(
        f"starting backtest with start_date={start_date}, end_date={end_date} w/ configuration={conf_dict}"
    )
    uid = str(uuid.uuid4())

    config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(
            enhanced_backtest.backtest_main(
                uid,
                start_date,
                end_date,
                TimeScale.day,
                conf_dict,
                0.0,
                0.0,
                AssetType.US_EQUITIES,
            )
        )
    except KeyboardInterrupt:
        tlog("backtest() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"backtest() - exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()
    else:
        loop.run_until_complete(
            save_optimizer_session(optimizer_session_id, uid, hypers)
        )
    finally:
        print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
        print(f"new batch-id: {uid}")
