import asyncio
import importlib.util
import json
import os
import sys
import traceback
from datetime import date, datetime, timedelta
from multiprocessing import Queue
from queue import Empty
from typing import Any, Dict, List

import pandas as pd
import pygit2
from alpaca_trade_api.entity import Order
from alpaca_trade_api.rest import APIError
from pandas import DataFrame as df
from pytz import timezone

from liualgotrader.common import config, market_data, trading_data
from liualgotrader.common.data_loader import DataLoader
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.fincalcs.data_conditions import (QUOTE_SKIP_CONDITIONS,
                                                    TRADE_CONDITIONS)
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.models.trending_tickers import TrendingTickers
from liualgotrader.strategies.base import Strategy, StrategyType
from liualgotrader.trading.base import Trader
from liualgotrader.trading.trader_factory import trader_factory

shortable: Dict = {}
symbol_data_error: Dict = {}
rejects: Dict[str, List[str]] = {}

nyc = timezone("America/New_York")


async def end_time(reason: str):
    for s in trading_data.strategies:
        tlog(f"updating end time for strategy {s.name}")
        await s.algo_run.update_end_time(
            pool=config.db_conn_pool, end_reason=reason
        )


async def liquidator(trader: Trader) -> None:
    tlog("liquidator() task starting")
    try:
        to_market_close = trader.get_time_market_close() - timedelta(
            minutes=15
        )

        tlog(f"liquidator() - waiting for market close: {to_market_close}")
        await asyncio.sleep(to_market_close.total_seconds())

    except asyncio.CancelledError:
        tlog("liquidator() cancelled during sleep")
    except KeyboardInterrupt:
        tlog("liquidator() - Caught KeyboardInterrupt")

    tlog("liquidator() -> starting to liquidate positions")
    try:
        for symbol in trading_data.positions:
            tlog(f"liquidator() -> checking {symbol}")
            if (
                trading_data.positions[symbol] != 0
                and trading_data.last_used_strategy[symbol].type
                == StrategyType.DAY_TRADE
            ):
                retry = 5
                while retry:
                    try:
                        await liquidate(
                            symbol,
                            int(trading_data.positions[symbol]),
                            trader,
                        )
                        break
                    except ConnectionError:
                        await trader.reconnect()
                        await asyncio.sleep(1)
                        retry -= 1
            else:
                tlog(
                    f"liquidator(): {symbol} {trading_data.positions[symbol]} {trading_data.last_used_strategy[symbol].type} {trading_data.last_used_strategy[symbol].name}"
                )
    except asyncio.CancelledError:
        tlog("liquidator() cancelled")
    except KeyboardInterrupt:
        tlog("liquidator() - Caught KeyboardInterrupt")

    tlog("liquidator() task completed")


async def teardown_task(trader: Trader, task: asyncio.Task) -> None:
    tlog(f"consumer-teardown_task() - starting ")

    if not config.market_close:
        tlog(
            "we're probably in market schedule by-pass mode, exiting consumer-teardown_task()"
        )
        return

    to_market_close = trader.get_time_market_close()
    tlog(
        f"consumer-teardown_task() - waiting for market close: {to_market_close}"
    )

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 5)

        tlog("consumer-teardown_task() starting")
        await end_time("market close")

        tlog("consumer-teardown_task(): requesting tasks to cancel")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            tlog("consumer-teardown_task(): tasks are cancelled now")

    except asyncio.CancelledError:
        tlog("consumer-teardown_task() cancelled during sleep")
    except KeyboardInterrupt:
        tlog("consumer-teardown_task() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"consumer-teardown_task() - exception of type {type(e).__name__} with args {e.args}"
        )
        # asyncio.get_running_loop().stop()
    finally:
        tlog("consumer-teardown_task() task done.")


async def liquidate(
    symbol: str,
    symbol_position: int,
    trader: Trader,
) -> None:

    if symbol_position and symbol not in trading_data.open_orders:
        tlog(
            f"Trading over, trying to liquidate remaining position {symbol_position} in {symbol}"
        )
        try:
            if symbol_position < 0:
                o = trader.submit_order(
                    symbol=symbol,
                    qty=str(-symbol_position),
                    side="buy",
                    type="market",
                    time_in_force="day",
                )
                op = "buy"
                trading_data.buy_indicators[symbol] = {"liquidation": 1}

            else:
                o = trader.submit_order(
                    symbol=symbol,
                    qty=str(symbol_position),
                    side="sell",
                    type="market",
                    time_in_force="day",
                )
                op = "sell"
                trading_data.sell_indicators[symbol] = {"liquidation": 1}

            trading_data.open_orders[symbol] = (o, op)
            trading_data.open_order_strategy[
                symbol
            ] = trading_data.last_used_strategy[symbol]

        except Exception as e:
            tlog(f"failed to liquidate {symbol} w exception {e}")


async def should_cancel_order(order: Order, market_clock: datetime) -> bool:
    # Make sure the order's not too old
    submitted_at = order.submitted_at.astimezone(timezone("America/New_York"))
    order_lifetime = market_clock - submitted_at
    return market_clock > submitted_at and order_lifetime.seconds // 60 >= 1


async def save(
    symbol: str,
    new_qty: int,
    last_op: str,
    price: float,
    indicators: Dict[Any, Any],
    now: str,
) -> None:
    db_trade = NewTrade(
        algo_run_id=trading_data.open_order_strategy[symbol].algo_run.run_id,
        symbol=symbol,
        qty=new_qty,
        operation=last_op,
        price=price,
        indicators=indicators,
    )

    await db_trade.save(
        config.db_conn_pool,
        str(now),
        trading_data.stop_prices[symbol]
        if symbol in trading_data.stop_prices
        else 0.0,
        trading_data.target_prices[symbol]
        if symbol in trading_data.target_prices
        else 0.0,
    )


async def update_partially_filled_order(
    strategy: Strategy, order: Order
) -> None:
    qty = int(order.filled_qty)
    new_qty = qty - abs(trading_data.partial_fills.get(order.symbol, 0))
    if order.side == "sell":
        qty *= -1

    trading_data.positions[order.symbol] = trading_data.positions.get(
        order.symbol, 0
    ) - trading_data.partial_fills.get(order.symbol, 0)
    trading_data.partial_fills[order.symbol] = qty
    trading_data.positions[order.symbol] += qty
    trading_data.open_orders[order.symbol] = (
        order,
        trading_data.open_orders.get(order.symbol)[1],  # type: ignore
    )

    try:
        indicators = {
            "buy": trading_data.buy_indicators.get(order.symbol, None),
            "sell": trading_data.sell_indicators.get(order.symbol, None),
        }
    except KeyError:
        indicators = {}

    await save(
        order.symbol,
        int(new_qty),
        order.side,
        float(order.filled_avg_price),
        indicators,
        order.updated_at,
    )

    if order.side == "buy":
        await strategy.buy_callback(
            order.symbol, float(order.filled_avg_price), int(new_qty)
        )
    else:
        await strategy.sell_callback(
            order.symbol, float(order.filled_avg_price), int(new_qty)
        )


async def update_filled_order(strategy: Strategy, order: Order) -> None:
    qty = int(order.filled_qty)
    new_qty = qty - abs(trading_data.partial_fills.get(order.symbol, 0))
    if order.side == "sell":
        qty *= -1

    trading_data.positions[order.symbol] = trading_data.positions.get(
        order.symbol, 0
    ) - trading_data.partial_fills.get(order.symbol, 0)
    trading_data.partial_fills[order.symbol] = 0
    trading_data.positions[order.symbol] += qty

    try:
        indicators = {
            "buy": trading_data.buy_indicators.get(order.symbol, None),
            "sell": trading_data.sell_indicators.get(order.symbol, None),
        }
    except KeyError:
        indicators = {}

    await save(
        order.symbol,
        int(new_qty),
        order.side,
        float(order.filled_avg_price),
        indicators,
        order.filled_at,
    )

    if order.side == "buy":
        trading_data.buy_indicators.pop(order.symbol, None)
        await strategy.buy_callback(
            order.symbol, float(order.filled_avg_price), int(new_qty)
        )
    else:
        trading_data.sell_indicators.pop(order.symbol, None)
        await strategy.sell_callback(
            order.symbol, float(order.filled_avg_price), int(new_qty)
        )

    trading_data.open_orders.pop(order.symbol, None)
    trading_data.open_order_strategy.pop(order.symbol, None)


async def handle_trade_update_for_order(data: Dict) -> bool:
    symbol = data["symbol"]

    last_order = trading_data.open_orders.get(symbol)[0]  # type: ignore
    if last_order is not None:
        event = data["event"]
        tlog(f"trade update for {symbol} data={data} with event {event}")

        if event == "partial_fill":
            await update_partially_filled_order(
                trading_data.open_order_strategy[symbol], Order(data["order"])
            )
        elif event == "fill":
            await update_filled_order(
                trading_data.open_order_strategy[symbol], Order(data["order"])
            )
        elif event in ("canceled", "rejected"):
            trading_data.partial_fills.pop(symbol, None)
            trading_data.open_orders.pop(symbol, None)
            trading_data.open_order_strategy.pop(symbol, None)

        return True
    else:
        tlog(
            f"[ERROR][{data['event']} trade update for {symbol} WITHOUT ORDER, should not arrive here"
        )
    return False


async def handle_trade_update_wo_order(data: Dict) -> bool:
    symbol = data["symbol"]
    event = data["event"]
    tlog(
        f"trade update without order for {symbol} data={data} with event {event}"
    )

    if event == "partial_fill":
        await update_partially_filled_order(
            trading_data.last_used_strategy[symbol], Order(data["order"])
        )
    elif event == "fill":
        await update_filled_order(
            trading_data.last_used_strategy[symbol], Order(data["order"])
        )
    elif event in ("canceled", "rejected"):
        trading_data.partial_fills.pop(symbol, None)

    return True


async def handle_trade_update(data: Dict) -> bool:
    symbol = data["symbol"]
    if trading_data.open_orders.get(symbol):
        return await handle_trade_update_for_order(data)
    else:
        return await handle_trade_update_wo_order(data)


async def handle_transaction(data: Dict) -> bool:
    if "conditions" in data and any(
        item in data["conditions"] for item in TRADE_CONDITIONS
    ):
        # tlog(f"trade={data}")
        return True
    return True


async def handle_quote(data: Dict) -> bool:
    if "askprice" not in data or "bidprice" not in data:
        return True
    if "condition" in data and data["condition"] in QUOTE_SKIP_CONDITIONS:
        return True

    symbol = data["symbol"]
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
    data_loader: DataLoader, data: Dict, ts: pd.Timestamp
) -> None:
    symbol = data["symbol"]
    try:
        current = data_loader[symbol].loc[ts]
    except KeyError:
        current = None

    if current is None:
        new_data = [
            data["open"],
            data["high"],
            data["low"],
            data["close"],
            data["volume"],
            data["average"],
            data["count"],
            data["vwap"],
        ]
    else:
        new_data = [
            current.open,
            max(data["high"], current.high),
            min(data["low"], current.low),
            data["close"],
            current.volume + data["volume"],
            data["average"],
            data["count"],
            data["vwap"],
        ]
    try:
        data_loader[symbol].loc[ts] = new_data
    except ValueError:
        print(f"loaded for {symbol}")
        data_loader[symbol][-1]
        data_loader[symbol].loc[ts] = new_data

    market_data.volume_today[symbol] = data["totalvolume"]


async def order_inflight(symbol, existing_order, original_ts, trader) -> bool:
    existing_order = existing_order[0]
    try:
        if await should_cancel_order(existing_order, original_ts):
            inflight_order = await trader.get_order(existing_order.id)
            if inflight_order and inflight_order.status == "filled":
                tlog(
                    f"order_id {existing_order.id} for {symbol} already filled {inflight_order}"  # type: ignore
                )
                await update_filled_order(
                    trading_data.open_order_strategy[symbol],
                    inflight_order,
                )
            elif (
                inflight_order and inflight_order.status == "partially_filled"
            ):
                tlog(
                    f"order_id {existing_order.id} for {symbol} already partially_filled {inflight_order}"  # type: ignore
                )
                await update_partially_filled_order(
                    trading_data.open_order_strategy[symbol],
                    inflight_order,
                )
            else:
                # Cancel it so we can try again for a fill
                tlog(
                    f"Cancel order id {existing_order.id} for {symbol} ts={original_ts} submission_ts={existing_order.submitted_at.astimezone(timezone('America/New_York'))}"  # type: ignore
                )
                await trader.cancel_order(existing_order.id)  # type: ignore
                trading_data.open_orders.pop(symbol, None)

        return True
    except AttributeError:
        tlog(f"Attribute Error in symbol {symbol} w/ {existing_order}")

    return False


async def execute_strategy_result(
    strategy: Strategy,
    trader: Trader,
    data_loader: DataLoader,
    symbol: str,
    what: Dict,
):
    try:
        if what["type"] == "limit":
            o = trader.submit_order(
                symbol=symbol,
                qty=what["qty"],
                side=what["side"],
                type="limit",
                time_in_force="day",
                limit_price=what["limit_price"],
            )
        else:
            o = trader.submit_order(
                symbol=symbol,
                qty=what["qty"],
                side=what["side"],
                type=what["type"],
                time_in_force="day",
            )

        trading_data.open_orders[symbol] = (o, what["side"])
        trading_data.open_order_strategy[symbol] = strategy

        await save(
            symbol=symbol,
            new_qty=0,
            last_op=str(what["side"]),
            price=0.0,
            indicators={},
            now=str(datetime.utcnow()),
        )

        tlog(
            f"executed strategy {strategy.name} on {symbol} w data {data_loader[symbol][-10:]}"
        )
        trading_data.last_used_strategy[symbol] = strategy
        if what["side"] == "buy":
            trading_data.buy_time[symbol] = datetime.now(
                tz=timezone("America/New_York")
            ).replace(second=0, microsecond=0)

    except APIError as e:
        tlog(
            f"Exception APIError with {e} from {what}, checking if order filled"
        )


async def do_strategies(
    trader: Trader,
    data_loader: DataLoader,
    symbol: str,
    position: int,
    now: pd.Timestamp,
    data: Dict,
) -> None:
    # run strategies
    for s in trading_data.strategies:
        if (
            "symbol_strategy" in data
            and data["symbol_strategy"]
            and s.name != data["symbol_strategy"]
        ):
            continue

        if s.name in rejects and symbol in rejects[s.name]:
            continue

        try:
            do, what = await s.run(
                symbol=symbol,
                shortable=shortable[symbol],
                position=position,
                minute_history=data_loader[symbol].symbol_data,
                now=now,
                portfolio_value=config.portfolio_value,
            )
        except Exception:
            traceback.print_exc()
            exc_info = sys.exc_info()
            lines = traceback.format_exception(*exc_info)
            for line in lines:
                tlog(f"{line}")
            del exc_info

        if do:
            await execute_strategy_result(
                strategy=s,
                trader=trader,
                data_loader=data_loader,
                symbol=symbol,
                what=what,
            )
        else:
            if what.get("reject", False):
                if s.name not in rejects:
                    rejects[s.name] = [symbol]
                else:
                    rejects[s.name].append(symbol)


async def handle_aggregate(
    trader: Trader,
    data_loader: DataLoader,
    symbol: str,
    ts: pd.Timestamp,
    data: Dict,
) -> bool:
    # Next, check for existing orders for the stock
    existing_order = trading_data.open_orders.get(symbol)

    if existing_order is not None and await order_inflight(
        symbol, existing_order, ts, trader
    ):
        return True

    # do we have a position?
    symbol_position = trading_data.positions.get(symbol, 0)

    # do we need to liquidate for the day?
    until_market_close = config.market_close - ts
    if (
        until_market_close.seconds // 60
        <= config.market_liquidation_end_time_minutes
        and symbol_position != 0
        and trading_data.last_used_strategy[symbol].type
        == StrategyType.DAY_TRADE
    ):
        await liquidate(symbol, symbol_position, trader)
    else:
        await do_strategies(
            trader=trader,
            data_loader=data_loader,
            symbol=symbol,
            position=symbol_position,
            now=ts,
            data=data,
        )

    return True


async def handle_data_queue_msg(
    data: Dict, trader: Trader, data_loader: DataLoader
) -> bool:
    global shortable
    global symbol_data_error
    global rejects

    symbol = data["symbol"]
    shortable[symbol] = True  # ToDO

    if data["EV"] == "T":
        return await handle_transaction(data)
    elif data["EV"] == "Q":
        return await handle_quote(data)

    elif data["EV"] in ("A", "AM"):
        original_ts = ts = pd.Timestamp(
            data["start"], tz="America/New_York", unit="ms"
        )
        ts = ts.replace(second=0, microsecond=0)

        await aggregate_bar_data(data_loader, data, ts)

        if data["EV"] == "A":
            if (time_diff := datetime.now(tz=timezone("America/New_York")) - original_ts) > timedelta(seconds=10):  # type: ignore
                tlog(f"A$ {symbol} too out of sync w {time_diff}")
                return False
            elif (
                datetime.now(tz=timezone("America/New_York")).replace(
                    second=0, microsecond=0
                )
                > ts
            ):
                return True
        elif data["EV"] == "AM":
            return True

        return await handle_aggregate(
            trader=trader,
            data_loader=data_loader,
            symbol=symbol,
            ts=original_ts,
            data=data,
        )

    return True


async def queue_consumer(
    queue: Queue, data_loader: DataLoader, trader: Trader
) -> None:
    tlog("queue_consumer() starting")
    try:
        while True:
            try:
                data = queue.get(timeout=2)
                if data["EV"] == "trade_update":
                    tlog(f"received trade_update: {data}")
                    await handle_trade_update(data)
                else:
                    if not await handle_data_queue_msg(
                        data, trader, data_loader
                    ):
                        while not queue.empty():
                            _ = queue.get()
                        tlog("cleaned queue")

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
                exc_info = sys.exc_info()
                lines = traceback.format_exception(*exc_info)
                for line in lines:
                    tlog(f"error: {line}")
                traceback.print_exception(*exc_info)
                del exc_info

    except asyncio.CancelledError:
        tlog("queue_consumer() cancelled ")
    except Exception as e:
        tlog(
            f"Exception in queue_consumer(): exception of type {type(e).__name__} with args {e.args}"
        )
        exc_info = sys.exc_info()
        lines = traceback.format_exception(*exc_info)
        for line in lines:
            tlog(f"error: {line}")
        traceback.print_exception(*exc_info)
        del exc_info
    finally:
        tlog("queue_consumer() task done.")


async def consumer_async_main(
    queue: Queue,
    symbols: List[str],
    unique_id: str,
    strategies_conf: Dict,
):
    await create_db_connection(str(config.dsn))
    data_loader = DataLoader()
    if symbols:
        try:
            trending_db = TrendingTickers(unique_id)
            await trending_db.save(symbols)
        except Exception as e:
            tlog(
                f"Exception in consumer_async_main() while storing symbols to DB:{type(e).__name__} with args {e.args}"
            )
            exc_info = sys.exc_info()
            lines = traceback.format_exception(*exc_info)
            for line in lines:
                tlog(f"error: {line}")
            traceback.print_exception(*exc_info)
            del exc_info

    trader = trader_factory()()
    config.market_open, config.market_close = trader.get_market_schedule()
    tlog(
        f"market open:{config.market_open} market close:{config.market_close}"
    )
    strategy_types = []
    for strategy_name in strategies_conf:
        strategy_details = strategies_conf[strategy_name]
        tlog(f"strategy {strategy_name} selected")

        if strategy_details.get("off_hours", False):
            tlog(f"{strategy_name} if off-hours, skipping during market hours")
        try:
            spec = importlib.util.spec_from_file_location(
                "module.name", strategy_details["filename"]
            )
            custom_strategy_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(custom_strategy_module)  # type: ignore
            class_name = strategy_name

            custom_strategy = getattr(custom_strategy_module, class_name)

            if not issubclass(custom_strategy, Strategy):
                tlog(f"strategy must inherit from class {Strategy.__name__}")
                exit(0)
            strategy_details.pop("filename", None)
            strategy_types += [(custom_strategy, strategy_details)]

        except FileNotFoundError as e:
            tlog(f"[Error] file not found `{strategy_details['filename']}`")
            exit(0)
        except Exception as e:
            tlog(
                f"[Error]exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()
            exit(0)

    loaded = 0
    for strategy_tuple in strategy_types:
        strategy_type = strategy_tuple[0]
        strategy_details = strategy_tuple[1]
        tlog(f"initializing {type(strategy_type).__name__}")
        s = strategy_type(
            batch_id=unique_id, data_loader=data_loader, **strategy_details
        )
        await s.create()

        trading_data.strategies.append(s)
        if symbols:
            loaded += await load_current_positions(
                trading_api=trader,
                symbols=symbols,
                strategy=s,
            )

    if symbols and loaded != len(symbols):
        tlog(
            f"[ERROR] Consumer process loaded only {loaded} out of {len(symbols)} open positions. HINT: make sure that your tradeplan.toml file includes all strategues in previous trading session."
        )

    queue_consumer_task = asyncio.create_task(
        queue_consumer(queue, data_loader, trader)
    )

    liquidate_task = asyncio.create_task(liquidator(trader))

    tear_down = asyncio.create_task(teardown_task(trader, queue_consumer_task))
    await asyncio.gather(
        tear_down,
        liquidate_task,
        queue_consumer_task,
        return_exceptions=True,
    )

    tlog("consumer_async_main() completed")


async def load_current_positions(
    trading_api: Trader,
    symbols: List[str],
    strategy: Strategy,
) -> int:
    loaded = 0
    for symbol in symbols:
        try:
            position = trading_api.get_position(symbol)
        except Exception as e:
            tlog(f"failed to load open position for {symbol} w/ {e}")
            continue

        if position:
            try:
                (
                    prev_run_id,
                    price,
                    stop_price,
                    target_price,
                    indicators,
                    timestamp,
                ) = await NewTrade.load_latest(
                    config.db_conn_pool,
                    symbol=symbol,
                    strategy_name=strategy.name,
                )

                if prev_run_id is None:
                    continue

                tlog(
                    f"loading current position for {symbol} for strategy {strategy.name}"
                )

                trading_data.positions[symbol] = int(position.qty)
                trading_data.stop_prices[symbol] = stop_price
                trading_data.target_prices[symbol] = target_price
                trading_data.latest_cost_basis[
                    symbol
                ] = trading_data.latest_scalp_basis[symbol] = price
                trading_data.open_order_strategy[symbol] = strategy
                trading_data.last_used_strategy[symbol] = strategy
                trading_data.buy_time[symbol] = timestamp.astimezone(tz=nyc)

                await NewTrade.rename_algo_run_id(
                    strategy.algo_run.run_id, prev_run_id, symbol
                )
                tlog(
                    f"moved {symbol} from {prev_run_id} to {strategy.algo_run.run_id}"
                )

                loaded += 1

            except ValueError:
                pass
            except Exception as e:
                tlog(
                    f"load_current_positions() for {symbol} could not load latest trade from db due to exception of type {type(e).__name__} with args {e.args}"
                )

    return loaded


def consumer_main(
    queue: Queue,
    symbols: List[str],
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

    config.bypass_market_schedule = conf.get("bypass_market_schedule", False)
    config.portfolio_value = conf.get("portfolio_value", None)
    if "risk" in conf:
        config.risk = conf["risk"]
    if "market_liquidation_end_time_minutes" in conf:
        config.market_liquidation_end_time_minutes = conf[
            "market_liquidation_end_time_minutes"
        ]

    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        asyncio.run(
            consumer_async_main(queue, symbols, unique_id, conf["strategies"])
        )
    except KeyboardInterrupt:
        tlog("consumer_main() - Caught KeyboardInterrupt")

    tlog("*** consumer_main() completed ***")
