"""
Execute Strategies on streaming data received from the Producer
"""
import asyncio
import os
from datetime import datetime, timedelta
from queue import Empty
from random import randint
from typing import Any, Dict, List, Optional

import pandas as pd
import pygit2
from mnqueues import MNQueue
from pandas import DataFrame as df
from pytz import timezone

from liualgotrader.analytics.analysis import load_trades_by_portfolio
from liualgotrader.common import config, market_data, trading_data
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import trace  # type: ignore
from liualgotrader.common.tlog import tlog, tlog_exception
from liualgotrader.common.tracer import trace_elapsed_metrics  # type: ignore
from liualgotrader.common.types import Order, Trade
from liualgotrader.fincalcs.data_conditions import QUOTE_SKIP_CONDITIONS
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.models.portfolio import Portfolio
from liualgotrader.models.tradeplan import TradePlan
from liualgotrader.models.trending_tickers import TrendingTickers
from liualgotrader.strategies.base import Strategy, StrategyType
from liualgotrader.trading.base import Trader
from liualgotrader.trading.trader_factory import (get_trader_by_name,
                                                  trader_factory)

shortable: Dict = {}
symbol_data_error: Dict = {}
rejects: Dict[str, List[str]] = {}
time_tick: Dict[str, datetime] = {}
nyc = timezone("America/New_York")


async def end_time(reason: str):
    for s in trading_data.strategies:
        tlog(f"updating end time for strategy {s.name}")
        await s.algo_run.update_end_time(
            pool=config.db_conn_pool, end_reason=reason
        )


def get_position(trader: Trader, symbol: str) -> float:
    try:
        return trader.get_position(symbol)
    except Exception:
        return 0


async def execute_run_all_results(
    strategy: Strategy,
    run_all_results: Dict[str, Dict],
    trader: Trader,
    data_loader: DataLoader,
):
    external_account_id = None
    if hasattr(strategy, "portfolio_id"):
        (
            external_account_id,
            broker_name,
        ) = await Portfolio.get_external_account_id(
            strategy.portfolio_id  # type: ignore
        )
        if broker_name:
            trader = get_trader_by_name(broker_name)

    for symbol, what in run_all_results.items():
        await execute_strategy_result(
            strategy,
            trader,
            data_loader,
            symbol.lower(),
            what,
            external_account_id,
        )


async def do_strategy_all(
    data_loader: DataLoader,
    trader: Trader,
    strategy: Strategy,
    symbols: List[str],
    carrier=None,
):
    try:
        now = datetime.now(nyc)
        symbols_position = {
            symbol.lower(): trading_data.positions[symbol]
            if symbol in trading_data.positions
            else get_position(trader, symbol)
            for symbol in symbols
        }
        do = await strategy.run_all(
            symbols_position=symbols_position,
            now=now,
            portfolio_value=config.portfolio_value,
            backtesting=True,
            data_loader=data_loader,
            trader=trader,
        )
        await execute_run_all_results(strategy, do, trader, data_loader)

    except Exception as e:
        if config.debug_enabled:
            tlog_exception("do_strategy_all")
        tlog(f"[Exception] {now} {strategy}->{e}")

        raise


async def cancel_lingering_orders(trader: Trader):
    tlog("cancel_lingering_orders() task starting")

    while True:
        await asyncio.sleep(60)

        if not len(trading_data.open_orders):
            continue

        ny_now = datetime.now(nyc)
        if not trader.is_market_open(ny_now):
            tlog("cancel_lingering_orders() market is closed")
            continue

        t = list(trading_data.open_orders.items())
        for symbol, order in t:
            await order_inflight(
                symbol=symbol,
                existing_order=order,
                now=ny_now,
                trader=trader,
            )


async def periodic_runner(data_loader: DataLoader, trader: Trader) -> None:
    try:
        while True:
            tlog("periodic_runner() task starting")
            # run strategies
            tasks = []
            for s in trading_data.strategies:
                try:
                    skip = not await s.should_run_all()
                except Exception:
                    skip = True
                finally:
                    if skip:
                        continue

                symbols = [
                    symbol.lower()
                    for symbol in trading_data.last_used_strategy
                    if trading_data.last_used_strategy[symbol.lower()] == s
                ]

                tasks.append(
                    asyncio.create_task(
                        trace({})(do_strategy_all)(
                            trader=trader,
                            data_loader=data_loader,
                            strategy=s,
                            symbols=symbols,
                        )
                    )
                )

            asyncio.gather(*tasks)
            await asyncio.sleep(5 * 60.0)

    except asyncio.CancelledError:
        tlog("periodic_runner() cancelled")
    except KeyboardInterrupt:
        tlog("periodic_runner() - Caught KeyboardInterrupt")
    except Exception as e:
        if config.debug_enabled:
            tlog_exception("periodic_runner")
        tlog(f"[EXCEPTION] periodic_runner: {e}")

    tlog("periodic_runner() task completed")


async def should_cancel_order(order: Order, market_clock: datetime) -> bool:
    # Make sure the order's not too old
    submitted_at = order.submitted_at.astimezone(market_clock.tzinfo)
    order_lifetime = market_clock - submitted_at

    if config.debug_enabled:
        tlog(
            f"should_cancel_order submitted_at:{submitted_at}, order_lifetime:{order_lifetime}"
        )
    return (
        market_clock > submitted_at
        and order_lifetime.total_seconds() // 60 >= 1
    )


async def save(
    symbol: str,
    new_qty: float,
    last_op: str,
    price: float,
    indicators: Dict[Any, Any],
    now: str,
    trade_fee=0.0,
) -> None:
    symbol = symbol.lower()
    db_trade = NewTrade(
        algo_run_id=trading_data.open_order_strategy[symbol].algo_run.run_id,
        symbol=symbol,
        qty=new_qty,
        operation=last_op,
        price=price,
        indicators=indicators,
    )

    await db_trade.save(config.db_conn_pool, now, trading_data.stop_prices[symbol]
        if symbol in trading_data.stop_prices
        else 0.0, trading_data.target_prices[symbol]
        if symbol in trading_data.target_prices
        else 0.0, trade_fee)


async def do_callbacks(
    symbol: str,
    strategy: Strategy,
    filled_qty: float,
    side: Order.FillSide,
    filled_avg_price: float,
):
    symbol = symbol.lower()
    if side == Order.FillSide.buy:
        trading_data.buy_indicators.pop(symbol, None)
        if strategy:
            await strategy.buy_callback(symbol, filled_avg_price, filled_qty)
    else:
        trading_data.sell_indicators.pop(symbol, None)
        if strategy:
            await strategy.sell_callback(symbol, filled_avg_price, filled_qty)


async def update_partially_filled_order(
    symbol: str,
    strategy: Strategy,
    filled_qty: float,
    side: Order.FillSide,
    filled_avg_price: float,
    updated_at: pd.Timestamp,
    trade_fee: float,
) -> None:
    symbol = symbol.lower()

    await do_callbacks(
        symbol=symbol,
        strategy=strategy,
        filled_qty=filled_qty,
        side=side,
        filled_avg_price=filled_avg_price,
    )

    trading_data.positions[symbol] = round(
        trading_data.positions.get(symbol, 0.0)
        + filled_qty * (1 if side == Order.FillSide.buy else -1),
        8,
    )

    try:
        indicators = {
            "buy": trading_data.buy_indicators.get(symbol, None),
            "sell": trading_data.sell_indicators.get(symbol, None),
        }
    except KeyError:
        indicators = {}

    await save(
        symbol,
        filled_qty,
        side.name,
        filled_avg_price,
        indicators,
        updated_at,
        trade_fee,
    )


async def update_filled_order(
    symbol: str,
    strategy: Strategy,
    filled_qty: float,
    side: Order.FillSide,
    filled_avg_price: float,
    updated_at: pd.Timestamp,
    trade_fee: float,
) -> None:
    symbol = symbol.lower()

    await update_partially_filled_order(
        symbol=symbol,
        strategy=strategy,
        filled_qty=filled_qty,
        side=side,
        filled_avg_price=filled_avg_price,
        updated_at=updated_at,
        trade_fee=trade_fee,
    )
    trading_data.open_orders.pop(symbol)
    if symbol in trading_data.open_order_strategy:
        trading_data.open_order_strategy.pop(symbol)

    tlog(
        f"update_filled_order open order for {symbol} popped. Position now {trading_data.positions[symbol]}"
    )


async def handle_trade_update_for_order(trade: Trade) -> bool:
    symbol = trade.symbol.lower()
    event = trade.event

    tlog(f"trade update for {symbol} with event {event}")

    if event == Order.EventType.partial_fill:
        await update_partially_filled_order(
            symbol=symbol,
            strategy=trading_data.open_order_strategy[symbol],
            filled_qty=trade.filled_qty,
            filled_avg_price=trade.filled_avg_price,
            side=trade.side,
            updated_at=trade.updated_at,
            trade_fee=trade.trade_fee,
        )

    elif event == Order.EventType.fill:
        await update_filled_order(
            symbol=symbol,
            strategy=trading_data.open_order_strategy[symbol],
            filled_qty=trade.filled_qty,
            filled_avg_price=trade.filled_avg_price,
            side=trade.side,
            updated_at=trade.updated_at,
            trade_fee=trade.trade_fee,
        )

    else:
        trading_data.partial_fills.pop(symbol, None)
        trading_data.partial_fills_fee.pop(symbol, None)
        trading_data.open_orders.pop(symbol, None)
        trading_data.open_order_strategy.pop(symbol, None)

    return True


async def handle_trade_update_wo_order(trade: Trade) -> bool:
    trade.symbol.lower()
    trade.event
    # tlog(f"trade update without order for {symbol} data={trade} with event {event}")
    return True


async def handle_trade_update(trade: Trade) -> bool:
    if trade.symbol.lower() in trading_data.open_orders:
        return await handle_trade_update_for_order(trade)
    else:
        return await handle_trade_update_wo_order(trade)


async def handle_quote(data: Dict) -> bool:
    if "askprice" not in data or "bidprice" not in data:
        return True
    if "condition" in data and data["condition"] in QUOTE_SKIP_CONDITIONS:
        return True

    symbol = data["symbol"].lower()
    # tlog(f"quote={data}")
    prev_ask = trading_data.voi_ask.get(symbol, None)
    prev_bid = trading_data.voi_bid.get(symbol, None)
    trading_data.voi_ask[symbol] = (
        data["askprice"],
        data["asksize"],
        data["timestamp"],
    )
    trading_data.voi_bid[symbol] = (
        data["bidprice"],
        data["bidsize"],
        data["timestamp"],
    )

    bid_delta_volume = (
        0
        if not prev_bid or data["bidprice"] < prev_bid[0]
        else 100 * data["bidsize"]
        if data["bidprice"] > prev_bid[0]
        else 100 * (data["bidsize"] - prev_bid[1])
    )
    ask_delta_volume = (
        0
        if not prev_ask or data["askprice"] > prev_ask[0]
        else 100 * data["asksize"]
        if data["askprice"] < prev_ask[0]
        else 100 * (data["asksize"] - prev_ask[1])
    )
    voi_stack = trading_data.voi.get(symbol, None)
    if not voi_stack:
        voi_stack = [0.0]
    elif len(voi_stack) == 10:
        voi_stack[0:9] = voi_stack[1:10]
        voi_stack.pop()

    k = 2.0 / (100 + 1)
    voi_stack.append(
        round(
            voi_stack[-1] * (1.0 - k)
            + k * (bid_delta_volume - ask_delta_volume),
            2,
        )
    )
    trading_data.voi[symbol] = voi_stack
    # tlog(f"{symbol} voi:{trading_data.voi[symbol]}")

    return True


async def aggregate_bar_data(
    data_loader: DataLoader, data: Dict, ts: pd.Timestamp, carrier=None
) -> None:
    symbol = data["symbol"].lower()

    if not data_loader.exist(symbol):
        # print(f"loading data for {symbol}...")
        data_loader[symbol][-1]

    try:
        current = data_loader[symbol].loc[ts]
    except KeyError:
        current = None

    if current is None or data["EV"] == "AM":
        new_data = [
            data["open"],
            data["high"],
            data["low"],
            data["close"],
            data["volume"],
            data["vwap"],
            data["average"],
            data["count"],
        ]
    else:
        new_data = [
            current["open"],
            max(data["high"], current["high"]),
            min(data["low"], current["low"]),
            data["close"],
            current["volume"] + data["volume"],
            data["vwap"] or current["vwap"],
            data["average"] or current["average"],
            data["count"] + current["count"],
        ]
    try:
        data_loader[symbol].loc[ts] = new_data
    except ValueError:
        print(f"loaded for {symbol} {new_data}")
        data_loader[symbol][-1]
        data_loader[symbol].loc[ts] = new_data

    market_data.volume_today[symbol] = (
        market_data.volume_today[symbol] + data["volume"]
        if symbol in market_data.volume_today
        else data["volume"]
    )


async def order_inflight(
    symbol: str,
    existing_order: Order,
    now: pd.Timestamp,
    trader: Trader,
) -> None:
    symbol = symbol.lower()
    try:
        if await should_cancel_order(existing_order, now):
            if config.debug_enabled:
                tlog(
                    f"should_cancel_order - checking status w/ order-id {existing_order.order_id}"
                )
            (
                order_status,
                filled_price,
                filled_qty,
                trade_fee,
            ) = await trader.is_order_completed(
                existing_order.order_id, existing_order.external_account_id
            )

            if order_status == Order.EventType.fill:
                tlog(
                    f"order_id {existing_order.order_id} for {symbol} already filled"
                )
                await update_filled_order(
                    symbol=symbol,
                    strategy=trading_data.open_order_strategy[symbol],  # type: ignore
                    filled_avg_price=filled_price,  # type: ignore
                    filled_qty=filled_qty,  # type: ignore
                    side=existing_order.side,  # type: ignore
                    updated_at=existing_order.submitted_at,  # type: ignore
                    trade_fee=trade_fee,  # type: ignore
                )
            elif order_status == Order.EventType.partial_fill:
                tlog(
                    f"order_id {existing_order.id} for {symbol} already partially_filled"  # type: ignore
                )
                await update_partially_filled_order(
                    symbol=symbol,
                    strategy=trading_data.open_order_strategy[symbol],
                    side=existing_order.side,  # type: ignore
                    filled_avg_price=filled_price,  # type: ignore
                    filled_qty=filled_qty,  # type: ignore
                    updated_at=existing_order.submitted_at,
                    trade_fee=trade_fee,  # type: ignore
                )
            else:
                # Cancel it so we can try again for a fill
                tlog(
                    f"Cancel order id {existing_order.order_id} for {symbol} ts={now} submission_ts={existing_order.submitted_at.astimezone(timezone('America/New_York'))}"  # type: ignore
                )
                if await trader.cancel_order(existing_order):
                    trading_data.open_orders.pop(symbol)

    except AttributeError as e:
        if config.debug_enabled:
            tlog_exception(f"order_inflight() w {e}")
        tlog(f"Attribute Error in symbol {symbol} w/ {existing_order}")
    except Exception as e:
        if config.debug_enabled:
            tlog_exception(f"order_inflight() w {e}")
        tlog(
            f"[EXCEPTION] order_inflight() : {e} for symbol {symbol} w/ {existing_order}"
        )


async def submit_order(
    trader: Trader, symbol: str, what: Dict, external_account_id: str = None
) -> Order:
    return (
        await trader.submit_order(
            symbol=symbol,
            qty=what["qty"],
            side=what["side"],
            order_type="limit",
            time_in_force="day",
            limit_price=what["limit_price"],
            on_behalf_of=external_account_id,
        )
        if what["type"] == "limit"
        else await trader.submit_order(
            symbol=symbol,
            qty=what["qty"],
            side=what["side"],
            order_type=what["type"],
            time_in_force="day",
            on_behalf_of=external_account_id,
        )
    )


async def update_trading_data(
    symbol: str, o: Order, strategy: Strategy, buy: bool
) -> None:
    trading_data.open_orders[symbol] = o
    trading_data.open_order_strategy[symbol] = strategy
    trading_data.last_used_strategy[symbol] = strategy
    if buy:
        trading_data.buy_time[symbol] = datetime.now(
            tz=timezone("America/New_York")
        ).replace(second=0, microsecond=0)


async def execute_strategy_result(
    strategy: Strategy,
    trader: Trader,
    data_loader: DataLoader,
    symbol: str,
    what: Dict,
    external_account_id: str = None,
) -> bool:
    tlog(f"execute_strategy_result for {symbol} do {what}")
    symbol = symbol.lower()

    o = await submit_order(trader, symbol, what, external_account_id)
    if not o:
        return False

    await update_trading_data(symbol, o, strategy, (what["side"] == "buy"))
    await save(
        symbol=symbol,
        new_qty=0,
        last_op=str(what["side"]),
        price=0.0,
        indicators={},
        now=str(datetime.utcnow()),
    )

    if config.debug_enabled:
        tlog(
            f"executed strategy {strategy.name} on {symbol} w data {data_loader[symbol][-10:]}"
        )

    return True


async def do_strategy(
    strategy: Strategy,
    symbol: str,
    shortable: bool,
    position: float,
    data_loader: DataLoader,
    trader: Trader,
    minute_history: df,
    now: pd.Timestamp,
    portfolio_value: Optional[float],
    carrier=None,
) -> bool:
    if not trader.is_market_open(datetime.now(nyc)):
        tlog(f"market closed, can't execute {symbol} @ {strategy.name}")
        return False

    do, what = await strategy.run(
        symbol=symbol,
        shortable=shortable,
        position=position,
        minute_history=minute_history,
        now=now,
        portfolio_value=portfolio_value,
    )

    return (
        await execute_strategy_result(
            strategy=strategy,
            trader=trader,
            data_loader=data_loader,
            symbol=symbol,
            what=what,
        )
        if do
        else not what.get("reject", False)
    )


async def _filter_strategies(symbol: str) -> List:
    return [
        s
        for s in trading_data.strategies
        if not await s.should_run_all()
        and symbol not in rejects.get(s.name, [])
    ]


async def do_strategies(
    trader: Trader,
    data_loader: DataLoader,
    symbol: str,
    position: float,
    now: pd.Timestamp,
    data: Dict,
    carrier=None,
) -> None:
    # run strategies
    strategies = await _filter_strategies(symbol)
    for s in strategies:
        try:
            if not await trace(carrier)(do_strategy)(
                strategy=s,
                symbol=symbol,
                shortable=shortable[symbol],
                position=position,
                minute_history=data_loader[symbol].symbol_data,
                now=pd.to_datetime(now.replace(nanosecond=0)).replace(
                    second=0, microsecond=0
                ),
                portfolio_value=config.portfolio_value,
                data_loader=data_loader,
                trader=trader,
            ):
                if s.name not in rejects:
                    rejects[s.name] = [symbol]
                else:
                    rejects[s.name].append(symbol)

        except Exception as e:
            tlog(f"[EXCEPTION] in do_strategies() : {e}")
            if config.debug_enabled:
                tlog_exception("do_strategies()")


async def handle_aggregate(
    trader: Trader,
    data_loader: DataLoader,
    symbol: str,
    ts: pd.Timestamp,
    data: Dict,
    carrier=None,
) -> bool:
    symbol = symbol.lower()

    if config.debug_enabled:
        tlog(f"handle_aggregate {symbol}")
    # Next, check for existing orders for the stock
    if symbol in trading_data.open_orders and await order_inflight(
        symbol, trading_data.open_orders[symbol.lower()], ts, trader
    ):
        return True

    await trace(carrier)(do_strategies)(
        trader=trader,
        data_loader=data_loader,
        symbol=symbol,
        position=trading_data.positions.get(symbol, 0),
        now=ts,
        data=data,
    )

    return True


async def handle_data_queue_msg(
    data: Dict, trader: Trader, data_loader: DataLoader, carrier=None
) -> bool:
    global shortable
    global symbol_data_error
    global rejects

    ts = pd.to_datetime(
        data["timestamp"].replace(second=0, microsecond=0, nanosecond=0)
    )
    symbol = data["symbol"].lower()
    shortable[symbol] = True  # TODO revisit collecting 'is shortable' data

    await trace(carrier)(aggregate_bar_data)(data_loader, data, ts)

    # timezone("America/New_York")
    time_diff = datetime.now(tz=data["timestamp"].tz) - data["timestamp"]
    if config.trace_enabled:
        trace_elapsed_metrics("DL", time_diff)

    if data["EV"] != "AM" and time_diff > timedelta(seconds=15):
        if randint(1, 100) == 1:  # nosec
            tlog(f"{data['EV']} {symbol} too out of sync w {time_diff}")
        return False

    if (
        time_tick.get(symbol)
        and data["timestamp"].replace(microsecond=0, nanosecond=0)
        == time_tick[symbol]
    ):
        return True

    time_tick[symbol] = data["timestamp"].replace(microsecond=0, nanosecond=0)
    await trace(carrier)(handle_aggregate)(
        trader=trader,
        data_loader=data_loader,
        symbol=symbol,
        ts=time_tick[symbol],
        data=data,
        carrier=None,
    )

    return True


async def queue_consumer(
    batch_id: str, queue: MNQueue, data_loader: DataLoader, trader: Trader
) -> None:
    tlog("queue_consumer() starting")
    try:
        while True:
            try:
                data = queue.get(timeout=2)
                if data["EV"] == "trade_update":
                    tlog(f"received trade_update: {data}")
                    await handle_trade_update(Trade(**data["trade"]))
                elif data["EV"] == "new_strategy":
                    tlog(f"received new_strategy: {data}")
                    await handle_new_strategy(
                        batch_id=batch_id,
                        data_loader=data_loader,
                        portfolio_id=data["portfolio_id"],
                        parameters=data["parameters"],
                    )
                else:
                    await trace({})(handle_data_queue_msg)(
                        data, trader, data_loader
                    )

            except Empty:
                await asyncio.sleep(0)
                continue
            except ConnectionError:
                await trader.reconnect()
                # re-post back to queue
                queue.put(data, timeout=1)
                await asyncio.sleep(1)
                continue
            except Exception as e:
                tlog(
                    f"Exception in queue_consumer(): exception of type {type(e).__name__} with args {e.args} inside loop"
                )
                if config.debug_enabled:
                    tlog_exception("queue_consumer")

    except asyncio.CancelledError:
        tlog("queue_consumer() cancelled ")
    except Exception as e:
        tlog(
            f"Exception in queue_consumer(): exception of type {type(e).__name__} with args {e.args}"
        )

        if config.debug_enabled:
            tlog_exception("queue_consumer")
    finally:
        tlog("queue_consumer() task done.")


async def create_strategies_from_file(
    batch_id: str,
    trader: Trader,
    data_loader: DataLoader,
    strategies_conf: Dict,
) -> List[Strategy]:
    strategy_list = []
    for strategy_name in strategies_conf:
        s = await Strategy.get_strategy(
            batch_id=batch_id,
            strategy_name=strategy_name,
            strategy_details=strategies_conf[strategy_name],
            data_loader=data_loader,
        )
        if s:
            strategy_list.append(s)

    return strategy_list


async def load_symbol_position(portfolio_id: str) -> Dict[str, float]:
    trades = load_trades_by_portfolio(portfolio_id)

    if not len(trades):
        return {}
    new_df = pd.DataFrame()
    new_df["symbol"] = trades.symbol.unique()
    new_df["qty"] = new_df.symbol.apply(
        lambda x: (
            trades[
                (trades.symbol == x) & (trades.operation == "buy")
            ].qty.sum()
        )
        - trades[(trades.symbol == x) & (trades.operation == "sell")].qty.sum()
    )
    new_df = new_df.loc[new_df.qty != 0]

    return {row.symbol: float(row.qty) for _, row in new_df.iterrows()}


async def create_strategies_from_db(
    batch_id: str,
    trader: Trader,
    data_loader: DataLoader,
) -> List[Strategy]:
    # load from tradeplan file
    trade_plan = await TradePlan.load()

    strategy_list = []
    for trade_plan_entry in trade_plan:
        strategy_details = trade_plan_entry.parameters
        strategy_details["portfolio_id"] = trade_plan_entry.portfolio_id

        strategy_name = strategy_details.pop("name")
        s = await Strategy.get_strategy(
            batch_id=batch_id,
            strategy_name=strategy_name,
            strategy_details=strategy_details,
            data_loader=data_loader,
        )
        if s:
            strategy_list.append(s)
            positions = await load_symbol_position(
                trade_plan_entry.portfolio_id
            )
            tlog(f"Loaded {len(positions)} positions for strategy_name")
            for symbol, qty in positions.items():
                trading_data.positions[symbol] = (
                    trading_data.positions.get(symbol, 0.0) + qty
                )

    return strategy_list


async def handle_new_strategy(
    batch_id: str, portfolio_id: str, parameters: dict, data_loader: DataLoader
):
    strategy_name = parameters.pop("name")
    parameters["portfolio_id"] = portfolio_id
    strategy = await Strategy.get_strategy(
        batch_id=batch_id,
        strategy_name=strategy_name,
        strategy_details=parameters,
        data_loader=data_loader,
    )

    if strategy:
        trading_data.strategies.append(strategy)


async def consumer_async_main(
    queue: MNQueue,
    unique_id: str,
    strategies_conf: Dict,
    file_only: bool,
):
    await create_db_connection(str(config.dsn))
    data_loader = DataLoader()

    trader = trader_factory()

    trading_data.strategies += await create_strategies_from_file(
        batch_id=unique_id,
        trader=trader,
        data_loader=data_loader,
        strategies_conf=strategies_conf,
    )

    if not file_only:
        trading_data.strategies += await create_strategies_from_db(
            batch_id=unique_id,
            trader=trader,
            data_loader=data_loader,
        )

    queue_consumer_task = asyncio.create_task(
        queue_consumer(unique_id, queue, data_loader, trader)
    )

    periodic_runner_task = asyncio.create_task(
        periodic_runner(data_loader, trader)
    )

    cancel_lingering_orders_task = asyncio.create_task(
        cancel_lingering_orders(trader)
    )

    await asyncio.gather(
        queue_consumer_task,
        periodic_runner_task,
        cancel_lingering_orders_task,
        return_exceptions=True,
    )

    tlog("consumer_async_main() completed")


def consumer_main(
    queue: MNQueue,
    unique_id: str,
    conf: Dict,
) -> None:
    tlog(f"*** consumer_main() starting w pid {os.getpid()} ***")

    try:
        config.build_label = pygit2.Repository("../").describe(
            describe_strategy=pygit2.GIT_DESCRIBE_TAGS
        )
    except pygit2.GitError:
        import liualgotrader

        config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore

    config.portfolio_value = conf.get("portfolio_value", None)
    if "risk" in conf:
        config.risk = conf["risk"]

    try:
        asyncio.run(
            consumer_async_main(
                queue,
                unique_id,
                conf["strategies"],
                conf.get("file_only", False),
            ),
        )
    except KeyboardInterrupt:
        tlog("consumer_main() - Caught KeyboardInterrupt")

    tlog("*** consumer_main() completed ***")
