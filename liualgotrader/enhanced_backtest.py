import asyncio
import inspect
import traceback
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import alpaca_trade_api as tradeapi
import pandas as pd
from pytz import timezone

from liualgotrader.common import config, trading_data
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog, tlog_exception
from liualgotrader.common.types import AssetType, TimeScale
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.scanners.base import Scanner  # type: ignore
from liualgotrader.scanners_runner import create_momentum_scanner
from liualgotrader.strategies.base import Strategy
from liualgotrader.trading.base import Trader
from liualgotrader.trading.trader_factory import trader_factory

run_scanners: Dict[Scanner, datetime] = {}
symbol_data: Dict[str, pd.DataFrame] = {}
portfolio_value: float = 100000


async def create_scanners(
    data_loader: DataLoader,
    scanners_conf: Dict,
    scanner_names: Optional[List],
) -> List[Scanner]:
    scanners: List = []
    for scanner_name in scanners_conf:
        if scanner_names and scanner_name not in scanner_names:
            continue
        tlog(f"scanner {scanner_name} selected")
        if scanner_name == "momentum":
            scanners.append(
                await create_momentum_scanner(
                    None, data_loader, scanners_conf[scanner_name]  # type: ignore
                )
            )
        else:
            scanners.append(
                await Scanner.get_scanner(
                    data_loader=data_loader,
                    scanner_name=scanner_name,
                    scanner_details=scanners_conf[scanner_name],
                )
            )

    return scanners


async def create_strategies(
    uid: str,
    conf_dict: Dict,
    dl: DataLoader,
    strategy_names: Optional[List],
) -> List[Strategy]:
    strategies = []
    config.env = "BACKTEST"

    for strategy_name in conf_dict:
        if strategy_names and strategy_name not in strategy_names:
            continue
        strategy_details = conf_dict[strategy_name]
        strategies.append(
            await Strategy.get_strategy(
                batch_id=uid,
                strategy_name=strategy_name,
                strategy_details=strategy_details,
                data_loader=dl,
            )
        )

    return strategies


async def do_scanners(
    now: datetime, scanners: List[Scanner], symbols: Dict
) -> Dict:
    for scanner in scanners:
        if scanner in run_scanners:
            if not scanner.recurrence:
                if now.date() == run_scanners[scanner].date():
                    continue
            elif (now - run_scanners[scanner]) < scanner.recurrence:
                continue

        run_scanners[scanner] = now
        new_symbols = await scanner.run(back_time=now)
        target_strategy_name = scanner.target_strategy_name

        target_strategy_name = target_strategy_name or "_all"

        symbols[target_strategy_name] = new_symbols

            # list(
            #    set(symbols.get(target_strategy_name, [])).union(set(new_symbols))
            # )

    return symbols


async def calculate_execution_price(
    symbol: str, data_loader: DataLoader, what: Dict, now: datetime
) -> float:
    if what["type"] == "market":
        return data_loader[symbol].close[now]

    price_limit = float(what["limit_price"])
    if what["side"] == "buy":
        if data_loader[symbol].close[now] <= price_limit:
            return data_loader[symbol].close[now]
        else:
            raise Exception(
                f"can not buy: limit price {price_limit} below market price {data_loader[symbol].close[now]}"
            )

    if data_loader[symbol].close[now] >= price_limit:
        return price_limit
    else:
        raise Exception(
            f"can not sell: limit price {price_limit} above market price {data_loader[symbol].close[now]}"
        )


async def do_strategy_result(
    data_loader: DataLoader,
    strategy: Strategy,
    symbol: str,
    now: datetime,
    what: Dict,
    buy_fee_percentage: float = 0.0,
    sell_fee_percentage: float = 0.0,
) -> bool:
    global portfolio_value

    qty = float(what["qty"])
    sign = (
        1
        if (
            what["side"] == "buy"
            and qty > 0
            or what["side"] == "sell"
            and qty < 0
        )
        else -1
    )

    try:
        price = await calculate_execution_price(
            symbol=symbol, data_loader=data_loader, what=what, now=now
        )
        if what["side"] == "buy":
            fee = price * qty * buy_fee_percentage / 100.0

            sig = inspect.signature(strategy.buy_callback)
            if "trade_fee" in sig.parameters:
                await strategy.buy_callback(symbol, price, qty, now, fee)
            else:
                await strategy.buy_callback(symbol, price, qty, now)

        elif what["side"] == "sell":
            fee = price * qty * sell_fee_percentage / 100.0
            sig = inspect.signature(strategy.buy_callback)
            if "trade_fee" in sig.parameters:
                await strategy.sell_callback(symbol, price, qty, now, fee)
            else:
                await strategy.sell_callback(symbol, price, qty, now)
    except Exception as e:
        tlog(
            f"do_strategy_result({symbol}, {what}, {now}) failed w/ {e}. operation not executed"
        )
        return False

    try:
        trading_data.positions[symbol] = (
            trading_data.positions[symbol] + sign * qty
        )
    except KeyError:
        trading_data.positions[symbol] = sign * qty

    trading_data.buy_time[symbol] = now.replace(second=0, microsecond=0)
    trading_data.last_used_strategy[symbol] = strategy

    db_trade = NewTrade(
        algo_run_id=strategy.algo_run.run_id,
        symbol=symbol,
        qty=qty,
        operation=what["side"],
        price=price,
        indicators={},
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
        fee,
    )

    return True


async def do_strategy_all(
    data_loader: DataLoader,
    now: pd.Timestamp,
    strategy: Strategy,
    symbols: List[str],
    trader: Trader,
    buy_fee_percentage: float,
    sell_fee_percentage: float,
):
    try:
        sig = inspect.signature(strategy.run_all)
        param = {
            "symbols_position": dict(
                {symbol: 0 for symbol in symbols}, **trading_data.positions
            ),
            "now": now.to_pydatetime(),
            "portfolio_value": portfolio_value,
            "backtesting": True,
            "data_loader": data_loader,
            "trader": trader,
        }
        if "fee_buy_percentage" in sig.parameters:
            param["fee_buy_percentage"] = buy_fee_percentage
        if "fee_sell_percentage" in sig.parameters:
            param["fee_sell_percentage"] = sell_fee_percentage
        do = await strategy.run_all(**param)
        items = list(do.items())
        items.sort(key=lambda x: int(x[1]["side"] == "buy"))
        for symbol, what in items:
            await do_strategy_result(
                data_loader,
                strategy,
                symbol,
                now,
                what,
                buy_fee_percentage,
                sell_fee_percentage,
            )

    except Exception as e:
        tlog(f"[Exception] {now} {strategy}->{e}")
        traceback.print_exc()
        raise


async def do_strategy_by_symbol(
    data_loader: DataLoader,
    now: pd.Timestamp,
    strategy: Strategy,
    symbols: List[str],
):
    global portfolio_value
    for symbol in symbols:
        try:
            _ = data_loader[symbol][now - timedelta(days=1) : now]  # type: ignore
            do, what = await strategy.run(
                symbol=symbol,
                shortable=True,
                position=trading_data.positions.get(symbol, 0.0),
                now=now,
                portfolio_value=portfolio_value,
                backtesting=True,
                minute_history=data_loader[symbol].symbol_data[:now],  # type: ignore
            )

            if do:
                await do_strategy_result(
                    data_loader, strategy, symbol, now, what
                )
        except ValueError:
            tlog(
                f"symbol {symbol} for now have data in the range {now - timedelta(days=1)}-{now}"
            )
        except Exception as e:
            tlog(f"[Exception] {now} {strategy}({symbol}):`{e}`")
            if config.debug_enabled:
                traceback.print_exc()
            raise


async def do_strategy(
    data_loader: DataLoader,
    now: pd.Timestamp,
    strategy: Strategy,
    symbols: List[str],
    trader: Trader,
    buy_fee_percentage: float,
    sell_fee_percentage: float,
):
    if await strategy.should_run_all():
        await do_strategy_all(
            data_loader,
            now,
            strategy,
            symbols,
            trader,
            buy_fee_percentage,
            sell_fee_percentage,
        )
    else:
        await do_strategy_by_symbol(data_loader, now, strategy, symbols)


def get_day_start_end(asset_type, day):
    if asset_type == AssetType.US_EQUITIES:
        day_start = day.date.replace(
            hour=day.open.hour,
            minute=day.open.minute,
            tzinfo=timezone("America/New_York"),
        )
        day_end = day.date.replace(
            hour=day.close.hour,
            minute=day.close.minute,
            tzinfo=timezone("America/New_York"),
        )
    elif asset_type == AssetType.CRYPTO:
        day_start = pd.Timestamp(
            datetime.combine(day, datetime.min.time()),
            tzinfo=timezone("America/New_York"),
        )
        day_end = pd.Timestamp(
            datetime.combine(day, datetime.max.time()),
            tzinfo=timezone("America/New_York"),
        )
    else:
        raise AssertionError(
            f"get_day_start_end(): asset type {asset_type} not yet supported"
        )

    return day_start, day_end


async def backtest_day(
    day,
    scanners,
    symbols,
    strategies,
    scale,
    data_loader,
    asset_type: AssetType,
    trader: Trader,
    buy_fee_percentage: float,
    sell_fee_percentage: float,
):
    day_start, day_end = get_day_start_end(asset_type, day)
    print(day_start, day_end)
    current_time = day_start
    prefetched: List[str] = []
    while current_time < day_end:
        symbols = await do_scanners(current_time, scanners, symbols)
        trading_data.positions = {
            symbol: trading_data.positions[symbol]
            for symbol in trading_data.positions
            if trading_data.positions[symbol] != 0
        }

        prefetch = [
            item
            for sublist in symbols.values()
            for item in sublist
            if item not in prefetched
        ]
        for symbol in prefetch:
            tlog(f"Prefetch data for {symbol}@{day_start}-{day_end}")

            # try:
            data_loader[symbol][day_start:day_end]
            prefetched.append(symbol)
            # except ValueError:
            #    tlog(f"no data for {symbol} on {day_start}")

        for strategy in strategies:
            try:
                trading_data.positions.update(
                    {
                        symbol: 0
                        for symbol in symbols.get(strategy.name, [])
                        + symbols.get("_all", [])
                        if symbol not in trading_data.positions
                    }
                )
            except TypeError as e:
                if config.debug_enabled:
                    tlog_exception("backtest_day")

                tlog(
                    f"[EXCEPTION] {e} (hint: check scanner(s) return list of symbols?)"
                )
                raise

            strategy_symbols = list(
                set(symbols.get("_all", [])).union(
                    set(symbols.get(strategy.name, []))
                )
            )
            await do_strategy(
                data_loader,
                current_time,
                strategy,
                strategy_symbols,
                trader,
                buy_fee_percentage,
                sell_fee_percentage,
            )

        current_time += timedelta(seconds=scale.value)


async def backtest_time_range(
    from_date: date,
    to_date: date,
    scale: TimeScale,
    data_loader: DataLoader,
    buy_fee_percentage: float,
    sell_fee_percentage: float,
    asset_type: AssetType,
    scanners: Optional[List] = None,
    strategies: Optional[List] = None,
):
    trade_api = tradeapi.REST(
        key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
    )
    if asset_type == AssetType.US_EQUITIES:
        calendars = trade_api.get_calendar(str(from_date), str(to_date))
    elif asset_type == AssetType.CRYPTO:
        calendars = [
            t.date() for t in pd.date_range(from_date, to_date).to_list()
        ]
    else:
        raise AssertionError(f"Asset type {asset_type} not supported yet")

    symbols: Dict = {}

    for day in calendars:
        await backtest_day(
            day=day,
            scanners=scanners,
            symbols=symbols,
            strategies=strategies,
            scale=scale,
            data_loader=data_loader,
            asset_type=asset_type,
            trader=trader_factory(),
            buy_fee_percentage=buy_fee_percentage,
            sell_fee_percentage=sell_fee_percentage,
        )


async def backtest_main(
    uid: str,
    from_date: date,
    to_date: date,
    scale: TimeScale,
    tradeplan: Dict,
    buy_fee_percentage: float,
    sell_fee_percentage: float,
    asset_type: AssetType,
    scanners: Optional[List] = None,
    strategies: Optional[List] = None,
) -> None:
    tlog(
        f"Starting back-test from {from_date} to {to_date} with time scale {scale}"
    )
    if scanners:
        tlog(f"with scanners:{scanners}")
    if strategies:
        tlog(f"with strategies:{strategies}")

    if "portfolio_value" in tradeplan:
        global portfolio_value
        portfolio_value = tradeplan["portfolio_value"]

    await create_db_connection()

    data_loader = DataLoader(scale)

    scanners = (
        await create_scanners(data_loader, tradeplan["scanners"], scanners)
        if "scanners" in tradeplan
        else []
    )
    tlog(f"instantiated {len(scanners)} scanners")
    strategies = await create_strategies(
        uid, tradeplan["strategies"], data_loader, strategies
    )
    tlog(f"instantiated {len(strategies)} strategies")

    await backtest_time_range(
        from_date=from_date,
        to_date=to_date,
        scale=scale,
        data_loader=data_loader,
        buy_fee_percentage=buy_fee_percentage,
        sell_fee_percentage=sell_fee_percentage,
        asset_type=asset_type,
        scanners=scanners,
        strategies=strategies,
    )


def backtest(
    from_date: date,
    to_date: date,
    scale: TimeScale,
    config: Dict,
    scanners: Optional[List],
    strategies: Optional[List],
    asset_type: AssetType,
    buy_fee_percentage: float,
    sell_fee_percentage: float,
) -> str:
    uid = str(uuid.uuid4())
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(
            backtest_main(
                uid,
                from_date,
                to_date,
                scale,
                config,
                buy_fee_percentage,
                sell_fee_percentage,
                asset_type,
                scanners,
                strategies,
            )
        )
    except KeyboardInterrupt:
        tlog("backtest() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"backtest() - exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()
    finally:
        print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
        print(f"new batch-id: {uid}")

        return uid
