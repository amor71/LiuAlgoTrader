#!/usr/bin/env python

import asyncio
import getopt
import os
import pprint
import sys
import traceback
import uuid
import toml
import pandas as pd
import importlib.util
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional

import alpaca_trade_api as tradeapi
import pygit2
import pytz
from requests.exceptions import HTTPError

from liualgotrader.common import config, market_data, trading_data
from liualgotrader.common.database import create_db_connection
from liualgotrader.common.decorators import timeit
from liualgotrader.common.tlog import tlog
from liualgotrader.fincalcs.vwap import add_daily_vwap
from liualgotrader.models.algo_run import AlgoRun
from liualgotrader.models.new_trades import NewTrade
from liualgotrader.models.trending_tickers import TrendingTickers
from liualgotrader.strategies.momentum_long import MomentumLong
from liualgotrader.strategies.base import Strategy, StrategyType
from liualgotrader.scanners.base import Scanner
from liualgotrader.scanners.momentum import Momentum


def get_batch_list():
    @timeit
    async def get_batch_list_worker():
        await create_db_connection()
        data = await AlgoRun.get_batches()
        pp = pprint.PrettyPrinter(indent=4)
        pp.pprint(data)

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
        f"usage: {sys.argv[0]} -d SYMBOL -v --batch-list --version --debug-symbol SYMBOL\n"
    )
    print("-v, --version\t\tDetailed version details")
    print(
        "--batch-list\tDisplay list of trading sessions, list limited to last 30 days"
    )
    print(
        "--debug-symbol\tWrite verbose debug information for symbol SYMBOL during back-testing"
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
) -> None:
    strategy_types = []
    for strategy in conf_dict["strategies"]:
        print(strategy)
        strategy_name = strategy
        strategy_details = conf_dict["strategies"][strategy_name]
        if strategy_name == "MomentumLong":
            tlog(f"strategy {strategy_name} selected")
            strategy_types += [(MomentumLong, strategy_details)]
        else:
            tlog(f"custom strategy {strategy_name} selected")

            try:
                spec = importlib.util.spec_from_file_location(
                    "module.name", strategy_details["filename"]
                )
                custom_strategy_module = importlib.util.module_from_spec(spec)
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
                tlog(f"[Error]exception of type {type(e).__name__} with args {e.args}")
                traceback.print_exc()
                exit(0)

    for strategy_tuple in strategy_types:
        strategy_type = strategy_tuple[0]
        strategy_details = strategy_tuple[1]
        config.env = "BACKTEST"
        tlog(f"initializing {strategy_type.name}")

        if "schedule" not in strategy_details:
            print("duration", duration)
            strategy_details["schedule"] = [
                {
                    "start": int(
                        (start - start.replace(hour=13, minute=30)).total_seconds()
                        // 60
                    ),
                    "duration": int(duration.total_seconds() // 60),
                }
            ]
            print(strategy_details["schedule"])
        s = strategy_type(batch_id=uid, ref_run_id=ref_run_id, **strategy_details)
        await s.create()
        trading_data.strategies.append(s)


def backtest(
    batch_id: str, debug_symbols: List[str] = None, conf_dict: Dict = None
) -> str:
    data_api: tradeapi = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )
    portfolio_value: float = 100000.0
    uid = str(uuid.uuid4())

    async def backtest_run(
        start: datetime, duration: timedelta, ref_run_id: int
    ) -> None:
        @timeit
        async def backtest_symbol(symbol: str, scanner_start_time: datetime) -> None:
            est = pytz.timezone("America/New_York")
            scanner_start_time = pytz.utc.localize(scanner_start_time).astimezone(est)
            start_time = pytz.utc.localize(start).astimezone(est)

            if scanner_start_time > start_time + duration:
                print(
                    f"{symbol} picked to late at {scanner_start_time} ({start_time}, {duration})"
                )
                return

            start_time = scanner_start_time
            if start_time.second > 0:
                start_time = start_time.replace(second=0, microsecond=0)
            print(
                f"--> back-testing {symbol} from {str(start_time)} duration {duration}"
            )
            if debug_symbols and symbol in debug_symbols:
                print("--> using DEBUG mode")

            # load historical data
            try:
                symbol_data = data_api.polygon.historic_agg_v2(
                    symbol,
                    1,
                    "minute",
                    _from=str(start_time - timedelta(days=8)),
                    to=str(start_time + timedelta(days=1)),
                    limit=10000,
                ).df
            except HTTPError as e:
                tlog(f"Received HTTP error {e} for {symbol}")
                return

            if len(symbol_data) < 100:
                tlog(f"not enough data-points  for {symbol}")
                return

            add_daily_vwap(symbol_data, debug=debug_symbols and symbol in debug_symbols)
            market_data.minute_history[symbol] = symbol_data
            print(
                f"loaded {len(market_data.minute_history[symbol].index)} agg data points"
            )

            position: int = 0
            minute_index = symbol_data["close"].index.get_loc(
                start_time, method="nearest"
            )
            new_now = symbol_data.index[minute_index]
            print(f"start time with data {new_now}")
            price = 0.0
            last_run_id = None
            # start_time + duration
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
                    do, what = await strategy.run(
                        symbol,
                        True,
                        position,
                        symbol_data[: minute_index + 1],
                        new_now,
                        portfolio_value,
                        debug=debug_symbols and symbol in debug_symbols,  # type: ignore
                        backtesting=True,
                    )
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
                    last_run_id = strategy.algo_run.run_id

                minute_index += 1
                new_now = symbol_data.index[minute_index]

            if position:
                if (
                    trading_data.last_used_strategy[symbol].type
                    == StrategyType.DAY_TRADE
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
                        config.db_conn_pool, str(symbol_data.index[minute_index - 1])
                    )

        symbols = await TrendingTickers.load(batch_id)
        print(f"loaded {len(symbols)}:\n {symbols}")

        if len(symbols) > 0:
            est = pytz.timezone("America/New_York")
            start_time = pytz.utc.localize(start).astimezone(est)
            config.market_open = start_time.replace(
                hour=9, minute=30, second=0, microsecond=0
            )
            config.market_close = start_time.replace(
                hour=16, minute=0, second=0, microsecond=0
            )
            print(f"market_open{config.market_open}")
            await create_strategies(conf_dict, duration, ref_run_id, uid, start)

            for symbol in symbols:
                await backtest_symbol(symbol[0], symbol[1])

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
                        [
                            w["duration"]
                            for w in [
                                item
                                for sublist in [
                                    conf_dict["strategies"][s]["schedule"]
                                    for s in conf_dict["strategies"]
                                ]
                                for item in sublist
                            ]
                        ]
                    )
                ),
                ref_run_id=run_ids[0],
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
        tlog(f"backtest() - exception of type {type(e).__name__} with args {e.args}")
        traceback.print_exc()
    finally:
        print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
        print(f"new batch-id: {uid}")
        return uid


def backtest_day(day: date, conf_dict: Dict) -> str:
    uid = str(uuid.uuid4())

    data_api: tradeapi = tradeapi.REST(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
    )

    async def backtest_worker(day: date) -> None:
        await create_db_connection()
        scanners_conf = conf_dict["scanners"]

        scanners: List[Optional[Scanner]] = []


        est = pytz.timezone("America/New_York")
        start_time = datetime.combine(day, datetime.min.time()).astimezone(est)
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
                        provider=scanner_details["provider"],
                        data_api=data_api,
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
                    tlog(f"instantiated momentum scanner")
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
                    custom_scanner_module = importlib.util.module_from_spec(spec)
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
                            data_api=data_api,
                            **scanner_details,
                        )
                    else:
                        recurrence = scanner_details.pop("recurrence")
                        scanner_object = custom_scanner(
                            data_api=data_api,
                            recurrence=timedelta(minutes=recurrence),
                            **scanner_details,
                        )

                except Exception as e:
                    tlog(
                        f"[Error] scanners_runner.scanners_runner() for {scanner_name}:{e} "
                    )
            if scanner_object:
                scanners.append(scanner_object)

        day = datetime.combine(day, datetime.min.time()).astimezone(est)

        start = day.replace(hour=9, minute=30)
        end = day.replace(hour=16, minute=0)

        await create_strategies(
            conf_dict,
            end - start,
            None,
            uid,
            day.replace(hour=9, minute=30, second=0, microsecond=0),
        )

        now = pd.Timestamp(start)

        symbols: List = []
        minute_history = {}
        portfolio_value: float = 100000.0
        while now < end:
            for i in range(0, len(scanners)):
                if now == start or (
                    scanners[i].recurrence is not None
                    and scanners[i].recurrence.total_seconds() > 0
                    and int((now - start).total_seconds() // 60)
                    % int(scanners[i].recurrence.total_seconds() // 60)
                    == 0
                ):
                    new_symbols = await scanners[i].run(now)
                    if new_symbols:
                        really_new = [x for x in new_symbols if x not in symbols]
                        if len(really_new) > 0:
                            print(f"Loading data for {len(really_new)} symbols: {really_new}")
                            minute_history = {
                                **minute_history,
                                **(
                                    market_data.get_historical_data_from_poylgon_for_symbols(
                                        data_api,
                                        really_new,
                                        start - timedelta(days=7),
                                        start + timedelta(days=1),
                                    )
                                ),
                            }
                            symbols += really_new
                            print(f"loaded data for {len(really_new)} stocks")

            for symbol in symbols:
                for strategy in trading_data.strategies:
                    minute_index = minute_history[symbol]["close"].index.get_loc(
                        now, method="nearest"
                    )
                    price = minute_history[symbol]["close"][minute_index]

                    if symbol not in trading_data.positions:
                        trading_data.positions[symbol] = 0

                    do, what = await strategy.run(
                        symbol,
                        True,
                        int(trading_data.positions[symbol]),
                        minute_history[symbol][: minute_index + 1],
                        now,
                        portfolio_value,
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
                            trading_data.positions[symbol] += int(float(what["qty"]))
                            trading_data.buy_time[symbol] = now.replace(
                                second=0, microsecond=0
                            )
                        else:
                            trading_data.positions[symbol] -= int(float(what["qty"]))

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
                            str(now),
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

            now += timedelta(minutes=1)

        for symbol in trading_data.positions:
                if (
                    trading_data.positions[symbol] != 0 and
                    trading_data.last_used_strategy[symbol].type
                    == StrategyType.DAY_TRADE
                ):
                    position = trading_data.positions[symbol]
                    minute_index = minute_history[symbol]["close"].index.get_loc(
                        now, method="nearest"
                    )
                    price = minute_history[symbol]["close"][minute_index]
                    tlog(f"[{end}]{symbol} liquidate {position} at {price}")
                    db_trade = NewTrade(
                        algo_run_id= trading_data.last_used_strategy[symbol].algo_run.run_id,  # type: ignore
                        symbol=symbol,
                        qty=int(position) if int(position) > 0 else -int(position),
                        operation="sell" if position > 0 else "buy",
                        price=price,
                        indicators={"liquidate": 1},
                    )
                    await db_trade.save(
                        config.db_conn_pool, str(price)
                    )
    try:
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(asyncio.new_event_loop())
        loop.run_until_complete(backtest_worker(day))
    except KeyboardInterrupt:
        tlog("backtest_day() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"backtest_day() - exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()
    finally:
        print("=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=")
        print(f"new batch-id: {uid}")
        return uid


if __name__ == "__main__":
    try:
        config.build_label = pygit2.Repository("../").describe(
            describe_strategy=pygit2.GIT_DESCRIBE_TAGS
        )
    except pygit2.GitError:
        import liualgotrader

        config.build_label = liualgotrader.__version__ if hasattr(liualgotrader, "__version__") else ""  # type: ignore

    config.filename = os.path.basename(__file__)
    folder = (
        config.tradeplan_folder
        if config.tradeplan_folder[-1] == "/"
        else f"{config.tradeplan_folder}/"
    )
    fname = f"{folder}{config.configuration_filename}"
    try:
        conf_dict = toml.load(fname)
        tlog(f"loaded configuration file from {fname}")
    except FileNotFoundError:
        tlog(f"[ERROR] could not locate tradeplan file {fname}")
        sys.exit(0)
    conf_dict = toml.load(config.configuration_filename)

    if len(sys.argv) == 1:
        show_usage()
        sys.exit(0)

    try:
        opts, args = getopt.getopt(
            sys.argv[1:], "vb:d:", ["batch-list", "version", "debug-symbol="]
        )
        debug_symbols = []
        for opt, arg in opts:
            if opt in ("-v", "--version"):
                show_version(config.filename, config.build_label)
                break
            elif opt in ("--batch-list", "-b"):
                get_batch_list()
                break
            elif opt in ("--debug-symbol", "-d"):
                debug_symbols.append(arg)

        for arg in args:
            backtest(arg, debug_symbols, conf_dict)

    except getopt.GetoptError as e:
        print(f"Error parsing options:{e}\n")
        show_usage()
        sys.exit(0)

    sys.exit(0)
