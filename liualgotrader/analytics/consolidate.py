from liualgotrader.analytics.analysis import load_trades_by_batch_id
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog


@timeit
async def trades(batch_id: str) -> None:
    """Go over all trades in a batch, and populate gain_loss table"""
    await create_db_connection()

    trades_data = load_trades_by_batch_id(batch_id=batch_id)

    if not trades_data.empty:
        tlog(f"loaded {len(trades_data)} trades")

    else:
        tlog(f"{batch_id} has no trades data")
