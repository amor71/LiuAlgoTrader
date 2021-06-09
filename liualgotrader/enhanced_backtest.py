import asyncio
import traceback
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
import pandas as pd
from pytz import timezone

from liualgotrader.common import config, trading_data
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.scanners.base import Scanner  # type: ignore
from liualgotrader.scanners_runner import create_momentum_scanner
from liualgotrader.strategies.base import Strategy

run_scanners: Dict[Scanner, datetime] = {}
symbol_data: Dict[str, pd.DataFrame] = {}
portfolio_value: float


async def create_scanners(
    data_loader: DataLoader,
    scanners_conf: Dict,
    scanner_names: Optional[List],
) -> List[Scanner]:
    scanners: List = []
    for scanner_name in scanners_conf:
        if scanner_names and scanner_name not in scanner_name:
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
        print(now, new_symbols, scanner.name)
        target_strategy_name = scanner.target_strategy_name

        target_strategy_name = (
            "_all" if not target_strategy_name else target_strategy_name
        )

        symbols[target_strategy_name] = list(
            set(symbols.get(target_strategy_name, [])).union(set(new_symbols))
        )

    return symbols


async def do_strategy_result(
    strategy: Strategy, symbol: str, now: datetime, what: Dict
) -> None:
    global portfolio_value

    sign = (
        1
        if (
            what["side"] == "buy"
            and float(what["qty"]) > 0
            or what["side"] == "sell"
            and float(what["qty"]) < 0
        )
        else -1
    )
    price = strategy.data_loader[symbol].close[now]  # type: ignore
    try:
        if what["side"] == "buy":
            await strategy.buy_callback(
                symbol, price, int(float(what["qty"])), now
            )
        elif what["side"] == "sell":
            await strategy.sell_callback(
                symbol, price, int(float(what["qty"])), now
            )
    except Exception as e:
        tlog(
            f"do_strategy_result({symbol}, {what} failed w/ {e}. operation not executed"
        )
        return

    try:
        trading_data.positions[symbol] = trading_data.positions[
            symbol
        ] + sign * int(float(what["qty"]))
    except KeyError:
        trading_data.positions[symbol] = sign * int(float(what["qty"]))
    trading_data.buy_time[symbol] = now.replace(second=0, microsecond=0)
    trading_data.last_used_strategy[symbol] = strategy

    db_trade = NewTrade(
        algo_run_id=strategy.algo_run.run_id,
        symbol=symbol,
        qty=int(float(what["qty"])),
        operation=what["side"],
        price=price,
        indicators={},
    )

    await db_trade.save(
        config.db_conn_pool,
        str(now),
        trading_data.stop_prices[symbol]
        if symbol in trading_data.stop_prices
        else None,
        trading_data.target_prices[symbol]
        if symbol in trading_data.target_prices
        else None,
    )


async def do_strategy_all(
    data_loader: DataLoader,
    now: pd.Timestamp,
    strategy: Strategy,
    symbols: List[str],
):
    try:
        do = await strategy.run_all(
            symbols_position=trading_data.positions,
            now=now.to_pydatetime(),
            portfolio_value=portfolio_value,
            backtesting=True,
            data_loader=data_loader,
        )
        items = list(do.items())
        items.sort(key=lambda x: int(x[1]["side"] == "buy"))
        for symbol, what in items:
            await do_strategy_result(strategy, symbol, now, what)

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
    print(strategy, symbols)
    for symbol in symbols:
        try:
            _ = data_loader[symbol][now - timedelta(days=30) : now]  # type: ignore
            do, what = await strategy.run(
                symbol=symbol,
                shortable=True,
                position=int(trading_data.positions.get(symbol, 0)),
                now=now,
                portfolio_value=portfolio_value,
                backtesting=True,
                minute_history=data_loader[symbol].symbol_data[:now],  # type: ignore
            )

            if do:
                await do_strategy_result(strategy, symbol, now, what)

        except Exception as e:
            tlog(f"[Exception] {now} {strategy}({symbol})->{e}")
            traceback.print_exc()
            raise


async def do_strategy(
    data_loader: DataLoader,
    now: pd.Timestamp,
    strategy: Strategy,
    symbols: List[str],
):
    global portfolio_value

    if await strategy.should_run_all():
        await do_strategy_all(data_loader, now, strategy, symbols)
    else:
        await do_strategy_by_symbol(data_loader, now, strategy, symbols)


async def backtest_main(
    uid: str,
    from_date: date,
    to_date: date,
    scale: TimeScale,
    tradeplan: Dict,
    scanners: Optional[List],
    strategies: Optional[List],
) -> None:
    tlog(
        f"Starting back-test from {from_date} to {to_date} with time scale {scale}"
    )
    if scanners:
        tlog(f"with scanners:{scanners}")
    if strategies:
        tlog(f"with strategies:{strategies}")

    global portfolio_value
    if "portfolio_value" in tradeplan:
        portfolio_value = tradeplan["portfolio_value"]
    else:
        portfolio_value = 100000

    await create_db_connection()

    data_loader = DataLoader(scale)
    trade_api = tradeapi.REST(
        key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
    )
    scanners = await create_scanners(
        data_loader, tradeplan["scanners"], scanners
    )
    tlog(f"instantiated {len(scanners)} scanners")
    strategies = await create_strategies(
        uid, tradeplan["strategies"], data_loader, strategies
    )
    tlog(f"instantiated {len(strategies)} strategies")
    calendars = trade_api.get_calendar(str(from_date), str(to_date))
    symbols: Dict = {}
    for day in calendars:
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

        config.market_open = day_start
        config.market_close = day_end
        current_time = day_start
        data_loader = DataLoader()
        while current_time < day_end:
            symbols = await do_scanners(current_time, scanners, symbols)

            for strategy in strategies:
                strategy_symbols = list(
                    set(symbols.get("_all", [])).union(
                        set(symbols.get(strategy.name, []))
                    )
                )
                await do_strategy(
                    data_loader, current_time, strategy, strategy_symbols
                )

            current_time += timedelta(seconds=scale.value)


def backtest(
    from_date: date,
    to_date: date,
    scale: TimeScale,
    config: Dict,
    scanners: Optional[List],
    strategies: Optional[List],
) -> str:
    uid = str(uuid.uuid4())
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(
            backtest_main(
                uid, from_date, to_date, scale, config, scanners, strategies
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
