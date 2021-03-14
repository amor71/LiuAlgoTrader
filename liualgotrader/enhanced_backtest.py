import asyncio
import traceback
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List

import alpaca_trade_api as tradeapi
import pandas as pd
from pytz import timezone

from liualgotrader.common import config, trading_data
from liualgotrader.common.data_loader import DataLoader, TimeScale
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.tlog import tlog
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.scanners.base import Scanner
from liualgotrader.scanners.momentum import Momentum
from liualgotrader.strategies.base import Strategy

run_scanners: Dict[Scanner, datetime] = {}
symbol_data: Dict[str, pd.DataFrame] = {}
portfolio_value: float


async def create_scanners(
    data_loader: DataLoader, scanners_conf: Dict
) -> List[Scanner]:
    scanners: List = []
    for scanner_name in scanners_conf:
        tlog(f"scanner {scanner_name} selected")
        if scanner_name == "momentum":
            tlog(
                "momentum scanner can not be supported in backtest on time-frame. skipping"
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
) -> List[Strategy]:
    strategies = []
    config.env = "BACKTEST"
    for strategy_name in conf_dict:
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
        if scanner in run_scanners and (
            not scanner.recurrence
            or (now - run_scanners[scanner]) < scanner.recurrence
        ):
            continue

        run_scanners[scanner] = now
        new_symbols = await scanner.run(back_time=now)
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
    if (
        what["side"] == "buy"
        and float(what["qty"]) > 0
        or what["side"] == "sell"
        and float(what["qty"]) < 0
    ):
        try:
            trading_data.positions[symbol] += int(float(what["qty"]))
        except KeyError:
            trading_data.positions[symbol] = int(float(what["qty"]))
        trading_data.buy_time[symbol] = now.replace(second=0, microsecond=0)
    else:
        try:
            trading_data.positions[symbol] -= int(float(what["qty"]))
        except KeyError:
            trading_data.positions[symbol] = -int(float(what["qty"]))

    trading_data.last_used_strategy[symbol] = strategy

    price = strategy.data_loader[symbol].close[now]  # type: ignore
    db_trade = NewTrade(
        algo_run_id=strategy.algo_run.run_id,
        symbol=symbol,
        qty=int(float(what["qty"])),
        operation=what["side"],
        price=price,
        indicators=trading_data.buy_indicators[symbol]
        if what["side"] == "buy"
        else trading_data.sell_indicators[symbol],
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

    if what["side"] == "buy":
        await strategy.buy_callback(symbol, price, int(float(what["qty"])))
    elif what["side"] == "sell":
        await strategy.sell_callback(symbol, price, int(float(what["qty"])))


async def do_strategy(
    data_loader: DataLoader,
    now: datetime,
    strategy: Strategy,
    symbols: List[str],
):
    global portfolio_value
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


async def backtest_main(
    uid: str, from_date: date, to_date: date, scale: TimeScale, tradeplan: Dict
) -> None:
    tlog(
        f"Starting back-test from {from_date} to {to_date} with time scale {scale}"
    )

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
    scanners = await create_scanners(data_loader, tradeplan["scanners"])
    strategies = await create_strategies(
        uid, tradeplan["strategies"], data_loader
    )
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
    from_date: date, to_date: date, scale: TimeScale, config: Dict
) -> str:
    uid = str(uuid.uuid4())
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(
            backtest_main(uid, from_date, to_date, scale, config)
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
