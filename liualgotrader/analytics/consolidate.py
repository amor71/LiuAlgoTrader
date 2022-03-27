import pandas as pd
from pandas import DataFrame, Timestamp

from liualgotrader.analytics.analysis import aload_trades_by_batch_id
from liualgotrader.common import config
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog
from liualgotrader.models.gain_loss import GainLoss, TradeAnalysis


@timeit
async def trades(batch_id: str) -> None:
    """Go over all trades in a batch, and populate gain_loss table"""

    if not len(batch_id):
        return

    await create_db_connection()
    trades_data = await aload_trades_by_batch_id(batch_id=batch_id)

    if trades_data.empty:
        tlog(f"loaded empty data-set in {batch_id}. aborting.")
        return

    tlog(f"loaded {len(trades_data)} trades")

    gain_loss = DataFrame(
        columns=[
            "symbol",
            "algo_run_id",
            "gain_percentage",
            "gain_value",
            "org_price",
        ]
    )

    trade_analysis = DataFrame(
        columns=[
            "symbol",
            "algo_run_id",
            "gain_percentage",
            "gain_value",
            "r_units",
            "initial_price",
            "stop_price",
            "org_price",
            "qty",
            "status",
        ]
    )
    for index, row in trades_data.iterrows():
        if row.price == 0:
            continue

        delta = float(
            row["price"]
            * row["qty"]
            * (1 if row["operation"] == "sell" and row["qty"] > 0 else -1)
        )

        if trade_analysis.loc[
            (trade_analysis.symbol == row.symbol)
            & (trade_analysis.algo_run_id == row.algo_run_id)
            & (trade_analysis.status == "open")
        ].empty:
            trade_analysis = pd.concat(
                [
                    trade_analysis,
                    pd.DataFrame(
                        data=[
                            {
                                "symbol": row.symbol,
                                "algo_run_id": row.algo_run_id,
                                "gain_value": delta,
                                "org_price": float(row.price * row.qty),
                                "start_time": Timestamp(row.client_time),
                                "qty": float(row.qty),
                                "r_units": float(row.price - row.stop_price)
                                if row.stop_price is not None
                                else 0,
                                "initial_price": float(row.price),
                                "stop_price": float(row.stop_price)
                                if row.stop_price is not None
                                else None,
                                "status": "open",
                                "sold_price": None,
                            }
                        ],
                    ),
                ],
                ignore_index=True,
            )
        else:
            trade_analysis.loc[
                (trade_analysis.symbol == row.symbol)
                & (trade_analysis.algo_run_id == row.algo_run_id)
                & (trade_analysis.status == "open"),
                "gain_value",
            ] += delta
            trade_analysis.loc[
                (trade_analysis.symbol == row.symbol)
                & (trade_analysis.algo_run_id == row.algo_run_id)
                & (trade_analysis.status == "open"),
                "qty",
            ] += float(
                row.qty
                * (-1 if row.operation == "sell" and row.qty > 0 else 1)
            )
            if not trade_analysis.loc[
                (trade_analysis.symbol == row.symbol)
                & (trade_analysis.algo_run_id == row.algo_run_id)
                & (trade_analysis.status == "open")
                & (trade_analysis.qty == 0.0)
            ].empty:
                trade_analysis.loc[
                    (trade_analysis.symbol == row.symbol)
                    & (trade_analysis.algo_run_id == row.algo_run_id)
                    & (trade_analysis.status == "open"),
                    "sold_price",
                ] = float(row.price)
                trade_analysis.loc[
                    (trade_analysis.symbol == row.symbol)
                    & (trade_analysis.algo_run_id == row.algo_run_id)
                    & (trade_analysis.status == "open"),
                    "r_units",
                ] = (
                    round(
                        float(
                            (
                                float(row.price)
                                - float(
                                    trade_analysis.loc[
                                        (trade_analysis.symbol == row.symbol)
                                        & (
                                            trade_analysis.algo_run_id
                                            == row.algo_run_id
                                        )
                                        & (trade_analysis.status == "open"),
                                        "initial_price",
                                    ]
                                )
                            )
                            / float(
                                trade_analysis.loc[
                                    (trade_analysis.symbol == row.symbol)
                                    & (
                                        trade_analysis.algo_run_id
                                        == row.algo_run_id
                                    )
                                    & (trade_analysis.status == "open"),
                                    "r_units",
                                ]
                            )
                        ),
                        2,
                    )
                    if trade_analysis.loc[
                        (trade_analysis.symbol == row.symbol)
                        & (trade_analysis.algo_run_id == row.algo_run_id)
                        & (trade_analysis.status == "open")
                        & (trade_analysis.r_units == 0.0)
                    ].empty
                    else None
                )
                trade_analysis.loc[
                    (trade_analysis.symbol == row.symbol)
                    & (trade_analysis.algo_run_id == row.algo_run_id)
                    & (trade_analysis.status == "open"),
                    "end_time",
                ] = Timestamp(row.client_time)
                trade_analysis.loc[
                    (trade_analysis.symbol == row.symbol)
                    & (trade_analysis.algo_run_id == row.algo_run_id)
                    & (trade_analysis.status == "open"),
                    "status",
                ] = "close"

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

        gain_loss["gain_percentage"] = round(
            100.0 * float(gain_loss["gain_value"] / gain_loss["org_price"]), 2
        )
        trade_analysis["gain_percentage"] = round(
            100.0
            * float(
                trade_analysis["gain_value"] / trade_analysis["org_price"]
            ),
            2,
        )

    await GainLoss.save(gain_loss)
    await TradeAnalysis.save(
        trade_analysis.loc[trade_analysis.status == "close"]
    )

    if len(trade_analysis) != len(
        trade_analysis.loc[trade_analysis.status == "close"]
    ):
        tlog(
            f"{batch_id} has {len(trade_analysis) -  len(trade_analysis.loc[trade_analysis.status == 'close'])} skipped open trades."
        )
