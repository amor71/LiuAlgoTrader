#!/usr/bin/env python

import asyncio
import importlib.util
import sys
import traceback
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import alpaca_trade_api as tradeapi
import nest_asyncio
import pandas as pd
import pytz
from requests.exceptions import HTTPError
from tabulate import tabulate

from liualgotrader.analytics.analysis import load_trades_by_batch_id
from liualgotrader.common import config, market_data, trading_data
from liualgotrader.common.data_loader import DataLoader  # type: ignore
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog
from liualgotrader.fincalcs.vwap import add_daily_vwap
from liualgotrader.models.algo_run import AlgoRun
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.models.trending_tickers import TrendingTickers
from liualgotrader.scanners.base import Scanner
from liualgotrader.scanners.momentum import Momentum
from liualgotrader.strategies.base import Strategy, StrategyType
from liualgotrader.trading.alpaca import AlpacaTrader


def get_batch_list():
    @timeit
    async def get_batch_list_worker():
        await create_db_connection()
        data = await AlgoRun.get_batches()
        print(
            tabulate(
                data,
                headers=["build", "batch_id", "strategy", "start time"],
            )
        )

    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(get_batch_list_worker())
    except KeyboardInterrupt:
        tlog("get_batch_list() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"get_batch_list() - exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()


"""
starting
"""


def show_usage():
    print(
        f"usage:\n{sys.argv[0]} batch --batch-list OR [--strict] [--symbol=SYMBOL] [--debug=SYMBOL] [--duration=<minutes>] <batch-id>",
        "\nOR"
        f"\n{sys.argv[0]} from <start_date> [--asset=equity(DEFAULT)|crypto][--scanners=<scanner-name,>] [--strats=<strategy-name,>] [--to=<end_date> DEFAULT is today] [--scale=day(DEFAULT)|minute [--buy-fee-percentage=0.(DEFAULT)] [--sell-fee-percentage=0.(DEFAULT)]",
    )
    msg = """
    'backter' application re-runs a past trading session, or test strategies on past data. 
    Re-run past sessions to test modified strategies or back-test new strategies on past data before running  
    on paper, or live accounts. To learn more, read LiuAlgoTrader online documentation.
    """
    print(msg)
    print("options:")
    print(
        "batch-list\t\tDisplay list of trading sessions, list limited to last 30 days"
    )
    print("symbol\t\t\tRun on specific SYMBOL, bypass batch-id scanners")
    print(
        "asset\t\t\tAsset type being traded. equity = US Equities, crypt = Crypto-currency. Asset type affects the market schedule for backtesting."
    )
    print(
        "duration\t\tRun back-test for number of <minutes>, bypass batch-id run duration"
    )
    print(
        "debug\t\t\tWrite verbose debug information for symbol SYMBOL during back-testing"
    )
    print(
        "strict\t\t\tRun back-test session only on same symbols traded in the original batch"
    )
    print(
        "to\t\t\tdate string in the format YYYY-MM-DD, if not provided current day is selected"
    )
    print("scale\t\t\ttime-scale for loading past data for back-test-ing")
    print(
        "buy-fee-percentage\tBroker fees as percentage from transaction. Represented as 0-1."
    )
    print(
        "sell-fee-percentage\tBroker fees as percentage from transaction. Represented as 0-1."
    )


def show_version(filename: str, version: str) -> None:
    """Display welcome message"""
    print(f"filename:{filename}\ngit version:{version}\n")


async def create_strategies(
    conf_dict: Dict,
    duration: timedelta,
    ref_run_id: Optional[int],
    uid: str,
    start: datetime,
    data_loader: DataLoader,
    bypass_strategy_duration: bool = False,
) -> None:
    strategy_types = []
    for strategy in conf_dict["strategies"]:
        print(strategy)
        strategy_name = strategy
        strategy_details = conf_dict["strategies"][strategy_name]
        if strategy_name == "MomentumLong":
            tlog(f"strategy {strategy_name} selected")
            strategy_types += [(strategy_details)]
        else:
            tlog(f"custom strategy {strategy_name} selected")

            try:
                spec = importlib.util.spec_from_file_location(
                    "module.name", strategy_details["filename"]
                )
                custom_strategy_module = importlib.util.module_from_spec(spec)  # type: ignore
                spec.loader.exec_module(custom_strategy_module)  # type: ignore
                class_name = strategy_name
                custom_strategy = getattr(custom_strategy_module, class_name)

                if not issubclass(custom_strategy, Strategy):
                    tlog(
                        f"custom strartegy must inherit from class {Strategy.__name__}"
                    )
                    exit(0)
                strategy_details.pop("filename", None)
                strategy_types += [(custom_strategy, strategy_details)]

            except Exception as e:
                tlog(
                    f"[Error]exception of type {type(e).__name__} with args {e.args}"
                )
                traceback.print_exc()
                exit(0)

    config.env = "BACKTEST"
    for strategy_tuple in strategy_types:
        strategy_type = strategy_tuple[0]
        strategy_details = strategy_tuple[1]
        tlog(f"initializing {strategy_type.__name__}")

        if "schedule" not in strategy_details:
            print("duration:", duration)
            strategy_details["schedule"] = [
                {
                    "start": int(
                        (
                            start - start.replace(hour=13, minute=30)
                        ).total_seconds()
                        // 60
                    ),
                    "duration": int(duration.total_seconds() // 60),
                }
            ]
        if bypass_strategy_duration:
            for schedule in strategy_details["schedule"]:
                schedule["duration"] = duration.total_seconds() // 60

        s = strategy_type(
            batch_id=uid,
            ref_run_id=ref_run_id,
            data_loader=data_loader,
            **strategy_details,
        )
        await s.create()
        trading_data.strategies.append(s)


@timeit
async def backtest_symbol(
    data_loader: DataLoader,
    portfolio_value: float,
    symbol: str,
    start: datetime,
    duration: timedelta,
    scanner_start_time: datetime,
    debug_symbol: bool = False,
) -> None:
    est = pytz.timezone("America/New_York")
    scanner_start_time = (
        pytz.utc.localize(scanner_start_time).astimezone(est)
        if scanner_start_time.tzinfo is None
        else scanner_start_time
    )
    start_time = pytz.utc.localize(start).astimezone(est)

    if scanner_start_time > start_time + duration:
        print(
            f"{symbol} picked too late at {scanner_start_time} ({start_time}, {duration})"
        )
        return

    start_time = scanner_start_time
    if start_time.second > 0:
        start_time = start_time.replace(second=0, microsecond=0)
    print(f"--> back-testing {symbol} from {start_time} duration {duration}")
    if debug_symbol:
        print("--> using DEBUG mode")

    symbol_data = pd.DataFrame(
        data_loader[symbol][start_time : start_time + duration]  # type: ignore
    )
    add_daily_vwap(
        symbol_data,
        debug=debug_symbol,
    )
    print(
        f"loaded {len(symbol_data)} agg data points({start_time}-{start_time + duration})"
    )

    minute_index = symbol_data["close"].index.get_loc(
        start_time, method="nearest"
    )

    position: int = 0
    new_now = symbol_data.index[minute_index]
    print(f"start time with data {new_now}")
    price = 0.0
    last_run_id = None

    # start_time + duration
    rejected: Dict[str, List] = {}
    while (
        new_now < config.market_close
        and minute_index < symbol_data.index.size - 1
    ):
        if symbol_data.index[minute_index] != new_now:
            print("mismatch!", symbol_data.index[minute_index], new_now)
            print(symbol_data["close"][minute_index - 10 : minute_index + 1])
            raise Exception()

        price = symbol_data["close"][minute_index]
        for strategy in trading_data.strategies:
            if debug_symbol:
                print(
                    f"Execute strategy {strategy.name} on {symbol} at {new_now}"
                )
            if symbol in rejected.get(strategy.name, []):
                continue

            try:
                do, what = await strategy.run(
                    symbol,
                    True,
                    position,
                    symbol_data[: minute_index + 1],
                    new_now,
                    portfolio_value,
                    debug=debug_symbol,  # type: ignore
                    backtesting=True,
                )
            except Exception as e:
                traceback.print_exc()
                tlog(
                    f"[ERROR] exception {e} on symbol {symbol} @ {strategy.name}"
                )
                continue

            if do:
                if (
                    what["side"] == "buy"
                    and float(what["qty"]) > 0
                    or what["side"] == "sell"
                    and float(what["qty"]) < 0
                ):
                    position += int(float(what["qty"]))
                    trading_data.buy_time[symbol] = new_now.replace(
                        second=0, microsecond=0
                    )
                else:
                    position -= int(float(what["qty"]))

                trading_data.last_used_strategy[symbol] = strategy

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
                    str(new_now),
                    trading_data.stop_prices[symbol],
                    trading_data.target_prices[symbol],
                )

                if what["side"] == "buy":
                    await strategy.buy_callback(
                        symbol, price, int(float(what["qty"]))
                    )
                    break
                elif what["side"] == "sell":
                    await strategy.sell_callback(
                        symbol, price, int(float(what["qty"]))
                    )
                    break
            elif what.get("reject", False):
                if strategy.name in rejected:
                    rejected[strategy.name].append(symbol)
                else:
                    rejected[strategy.name] = [symbol]

            last_run_id = strategy.algo_run.run_id

        minute_index += 1
        new_now = symbol_data.index[minute_index]

    if position and (
        trading_data.last_used_strategy[symbol].type == StrategyType.DAY_TRADE
    ):
        tlog(f"[{new_now}]{symbol} liquidate {position} at {price}")
        db_trade = NewTrade(
            algo_run_id=last_run_id,  # type: ignore
            symbol=symbol,
            qty=int(position) if int(position) > 0 else -int(position),
            operation="sell" if position > 0 else "buy",
            price=price,
            indicators={"liquidate": 1},
        )
        await db_trade.save(
            config.db_conn_pool,
            str(symbol_data.index[minute_index - 1]),
        )


def backtest(
    batch_id: str,
    conf_dict: Dict,
    debug_symbols: List[str],
    strict: bool = False,
    specific_symbols: List[str] = None,
    bypass_duration: int = None,
) -> str:
    data_loader = DataLoader()
    portfolio_value: float = (
        100000.0 if not config.portfolio_value else config.portfolio_value
    )
    uid = str(uuid.uuid4())

    async def backtest_run(
        start: datetime,
        duration: timedelta,
        ref_run_id: int,
        specific_symbols: List[str] = None,
    ) -> None:
        if specific_symbols:
            symbols_and_start_time: List = []
            for symbol in specific_symbols:
                symbols_and_start_time.append((symbol, start))
            num_symbols = len(specific_symbols)
        elif not strict:
            symbols_and_start_time = await TrendingTickers.load(batch_id)

            num_symbols = len(symbols_and_start_time)
        else:
            print("strict mode selected, loading symbols from trades")
            nest_asyncio.apply()
            _df = load_trades_by_batch_id(batch_id)
            symbols = _df.symbol.unique().tolist()
            num_symbols = len(symbols)
            est = pytz.timezone("America/New_York")
            start_time = pytz.utc.localize(_df.start_time.min()).astimezone(
                est
            )
            symbols_and_start_time = list(
                zip(symbols, [start_time for x in range(num_symbols)])
            )

        print(f"loaded {len(symbols_and_start_time)} symbols")

        if num_symbols > 0:
            est = pytz.timezone("America/New_York")
            start_time = pytz.utc.localize(start).astimezone(est)
            config.market_open = start_time.replace(
                hour=9, minute=30, second=0, microsecond=0
            )
            config.market_close = start_time.replace(
                hour=16, minute=0, second=0, microsecond=0
            )
            print(f"market_open {config.market_open}")
            await create_strategies(
                conf_dict,
                duration,
                ref_run_id,
                uid,
                start,
                DataLoader(),
                bypass_duration is not None,
            )

            for symbol_and_start_time in symbols_and_start_time:
                symbol = symbol_and_start_time[0]
                await backtest_symbol(
                    data_loader=data_loader,
                    portfolio_value=portfolio_value,
                    symbol=symbol,
                    start=start,
                    duration=duration,
                    scanner_start_time=symbol_and_start_time[1],
                    debug_symbol=symbol in debug_symbols,
                )

    @timeit
    async def backtest_worker() -> None:
        await create_db_connection()
        run_details = await AlgoRun.get_batch_details(batch_id)
        run_ids, starts, ends, _ = zip(*run_details)

        if not len(run_details):
            print(f"can't load data for batch id {batch_id}")
        else:
            await backtest_run(
                start=min(starts),
                duration=timedelta(
                    minutes=max(
                        w["duration"]
                        for w in [
                            item
                            for sublist in [
                                conf_dict["strategies"][s]["schedule"]  # type: ignore
                                for s in conf_dict["strategies"]  # type: ignore
                            ]
                            for item in sublist
                        ]
                    )
                    if not bypass_duration
                    else bypass_duration
                ),
                ref_run_id=run_ids[0],
                specific_symbols=specific_symbols,
            )

    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(backtest_worker())
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


class BackTestDay:
    def __init__(self, conf_dict: Dict):
        self.uid = str(uuid.uuid4())

        self.conf_dict = conf_dict
        config.portfolio_value = self.conf_dict.get("portfolio_value", None)
        self.data_loader = DataLoader()
        self.scanners: List[Scanner] = []

    async def create(self, day: date) -> str:
        await create_db_connection()
        scanners_conf = self.conf_dict["scanners"]

        est = pytz.timezone("America/New_York")
        start_time = datetime.combine(day, datetime.min.time()).astimezone(est)
        day = datetime.combine(day, datetime.min.time()).astimezone(est)
        self.start = day.replace(hour=9, minute=30)
        self.end = day.replace(hour=16, minute=0)

        config.market_open = start_time.replace(
            hour=9, minute=30, second=0, microsecond=0
        )
        config.market_close = start_time.replace(
            hour=16, minute=0, second=0, microsecond=0
        )
        for scanner_name in scanners_conf:
            scanner_object: Optional[Scanner] = None
            if scanner_name == "momentum":
                scanner_details = scanners_conf[scanner_name]
                try:
                    recurrence = scanner_details.get("recurrence", None)
                    target_strategy_name = scanner_details.get(
                        "target_strategy_name", None
                    )
                    scanner_object = Momentum(
                        data_loader=self.data_loader,
                        trading_api=AlpacaTrader(),
                        min_last_dv=scanner_details["min_last_dv"],
                        min_share_price=scanner_details["min_share_price"],
                        max_share_price=scanner_details["max_share_price"],
                        min_volume=scanner_details["min_volume"],
                        from_market_open=scanner_details["from_market_open"],
                        today_change_percent=scanner_details["min_gap"],
                        recurrence=timedelta(minutes=recurrence)
                        if recurrence
                        else None,
                        target_strategy_name=target_strategy_name,
                        max_symbols=scanner_details.get(
                            "max_symbols", config.total_tickers
                        ),
                    )
                    tlog("instantiated momentum scanner")
                except KeyError as e:
                    tlog(
                        f"Error {e} in processing of scanner configuration {scanner_details}"
                    )
                    exit(0)
            else:
                tlog(f"custom scanner {scanner_name} selected")
                scanner_details = scanners_conf[scanner_name]
                try:
                    spec = importlib.util.spec_from_file_location(
                        "module.name", scanner_details["filename"]
                    )
                    custom_scanner_module = importlib.util.module_from_spec(
                        spec  # type: ignore
                    )
                    spec.loader.exec_module(custom_scanner_module)  # type: ignore
                    class_name = scanner_name
                    custom_scanner = getattr(custom_scanner_module, class_name)

                    if not issubclass(custom_scanner, Scanner):
                        tlog(
                            f"custom scanner must inherit from class {Scanner.__name__}"
                        )
                        exit(0)

                    scanner_details.pop("filename")
                    if "recurrence" not in scanner_details:
                        scanner_object = custom_scanner(
                            data_loader=self.data_loader,
                            **scanner_details,
                        )
                    else:
                        recurrence = scanner_details.pop("recurrence")
                        scanner_object = custom_scanner(
                            data_loader=self.data_loader,
                            recurrence=timedelta(minutes=recurrence),
                            **scanner_details,
                        )

                except Exception as e:
                    tlog(
                        f"[Error] scanners_runner.scanners_runner() for {scanner_name}:{e} "
                    )
            if scanner_object:
                self.scanners.append(scanner_object)

        await create_strategies(
            self.conf_dict,
            self.end - self.start,
            None,
            self.uid,
            day.replace(hour=9, minute=30, second=0, microsecond=0),
            DataLoader(),
        )

        self.now = pd.Timestamp(self.start)
        self.symbols: List = []
        self.portfolio_value: float = (
            100000.0 if not config.portfolio_value else config.portfolio_value
        )
        if "risk" in self.conf_dict:
            config.risk = self.conf_dict["risk"]
        return self.uid

    async def next_minute(self) -> Tuple[bool, List[Optional[str]]]:
        rc_msg: List[Optional[str]] = []
        if self.now >= self.end:
            return False, []

        for i in range(len(self.scanners)):
            if self.now == self.start or (
                self.scanners[i].recurrence is not None
                and self.scanners[i].recurrence.total_seconds() > 0  # type: ignore
                and int((self.now - self.start).total_seconds() // 60)  # type: ignore
                % int(self.scanners[i].recurrence.total_seconds() // 60)  # type: ignore
                == 0
            ):
                new_symbols = await self.scanners[i].run(self.now)
                if new_symbols:
                    really_new = [
                        x for x in new_symbols if x not in self.symbols
                    ]
                    if really_new:
                        print(
                            f"Loading data for {len(really_new)} symbols: {really_new}"
                        )
                        rc_msg.append(
                            f"Loaded data for {len(really_new)} symbols: {really_new}"
                        )
                        self.symbols += really_new
                        print(f"loaded data for {len(really_new)} stocks")

        for symbol in self.symbols:
            try:
                for strategy in trading_data.strategies:

                    try:
                        minute_index = self.data_loader[symbol][
                            "close"
                        ].index.get_loc(self.now, method="nearest")
                    except Exception as e:
                        print(f"[Exception] {self.now} {symbol} {e}")
                        print(self.data_loader[symbol]["close"][-100:])
                        continue

                    price = self.data_loader[symbol]["close"][minute_index]

                    if symbol not in trading_data.positions:
                        trading_data.positions[symbol] = 0

                    do, what = await strategy.run(
                        symbol,
                        True,
                        int(trading_data.positions[symbol]),
                        self.data_loader[symbol][: minute_index + 1],
                        self.now,
                        self.portfolio_value,
                        debug=False,  # type: ignore
                        backtesting=True,
                    )
                    if do:
                        if (
                            what["side"] == "buy"
                            and float(what["qty"]) > 0
                            or what["side"] == "sell"
                            and float(what["qty"]) < 0
                        ):
                            trading_data.positions[symbol] += int(
                                float(what["qty"])
                            )
                            trading_data.buy_time[symbol] = self.now.replace(
                                second=0, microsecond=0
                            )
                        else:
                            trading_data.positions[symbol] -= int(
                                float(what["qty"])
                            )

                        trading_data.last_used_strategy[symbol] = strategy

                        rc_msg.append(
                            f"[{self.now}][{strategy.name}] {what['side']} {what['qty']} of {symbol} @ {price}"
                        )
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
                            str(self.now.to_pydatetime()),
                            trading_data.stop_prices[symbol],
                            trading_data.target_prices[symbol],
                        )

                        if what["side"] == "buy":
                            await strategy.buy_callback(
                                symbol, price, int(float(what["qty"]))
                            )
                            break
                        elif what["side"] == "sell":
                            await strategy.sell_callback(
                                symbol, price, int(float(what["qty"]))
                            )
                            break
            except Exception as e:
                print(f"[Exception] {self.now} {symbol} {e}")
                traceback.print_exc()

        self.now += timedelta(minutes=1)

        return True, rc_msg

    async def liquidate(self):
        for symbol in trading_data.positions:
            if (
                trading_data.positions[symbol] != 0
                and trading_data.last_used_strategy[symbol].type
                == StrategyType.DAY_TRADE
            ):
                position = trading_data.positions[symbol]
                minute_index = self.data_loader[symbol]["close"].index.get_loc(
                    self.now, method="nearest"
                )
                price = self.data_loader[symbol]["close"][minute_index]
                tlog(f"[{self.end}]{symbol} liquidate {position} at {price}")
                db_trade = NewTrade(
                    algo_run_id=trading_data.last_used_strategy[symbol].algo_run.run_id,  # type: ignore
                    symbol=symbol,
                    qty=int(position) if int(position) > 0 else -int(position),
                    operation="sell" if position > 0 else "buy",
                    price=price,
                    indicators={"liquidate": 1},
                )
                await db_trade.save(
                    config.db_conn_pool, str(self.now.to_pydatetime())
                )
