import asyncio
from decimal import Decimal

from pandas import DataFrame

from liualgotrader.analytics.analysis import aload_trades_by_batch_id
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog


@timeit
async def trades(batch_id: str) -> None:
    """Go over all trades in a batch, and populate gain_loss table"""

    if not len(batch_id):
        return

    await create_db_connection()
    await asyncio.sleep(1)
    trades_data = await aload_trades_by_batch_id(batch_id=batch_id)

    if trades_data.empty:
        tlog(f"loaded empty data-set in {batch_id}. aborting.")
        return

    tlog(f"loaded {len(trades_data)} trades")

    gain_loss = DataFrame(
        columns=[
            "symbol",
            "algo_run_id",
            "gain_precentage",
            "gain_value",
            "org_price",
        ]
    )
    for index, row in trades_data.iterrows():
        delta = float(
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )

        if gain_loss.loc[
            (gain_loss.symbol == row.symbol)
            & (gain_loss.algo_run_id == row.algo_run_id),
            "gain_value",
        ].empty:
            gain_loss = gain_loss.append(
                {
                    "symbol": row.symbol,
                    "algo_run_id": row.algo_run_id,
                    "gain_value": delta,
                    "org_price": float(row.price * row.qty),
                },
                ignore_index=True,
            )
        else:
            gain_loss.loc[
                (gain_loss.symbol == row.symbol)
                & (gain_loss.algo_run_id == row.algo_run_id),
                "gain_value",
            ] += delta

        gain_loss["gain_precentage"] = round(
            100.0 * gain_loss["gain_value"] / gain_loss["org_price"], 2
        )

    print(gain_loss)
