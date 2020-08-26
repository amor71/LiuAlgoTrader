"""
Get Market data from Polygon and pump to consumers
"""
import asyncio
import json
import os
import traceback
from datetime import datetime, timedelta
from multiprocessing import Queue
from typing import Dict, List

import alpaca_trade_api as tradeapi
from alpaca_trade_api.stream2 import StreamConn, polygon
from google.cloud import error_reporting
from pytz import timezone
from pytz.tzinfo import DstTzInfo

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog

last_msg_tstamp: datetime = datetime.now()


async def trade_run(
    ws: StreamConn, queues: List[Queue], queue_id_hash: Dict[str, int]
) -> None:

    tlog("trade_run() starting using Alpaca trading  ")
    # Use trade updates to keep track of our portfolio
    @ws.on(r"trade_update")
    async def handle_trade_update(conn, channel, data):

        try:
            tlog(f"TRADE UPDATE! {data.__dict__}")
            data.__dict__["_raw"]["EV"] = "trade_update"
            data.__dict__["_raw"]["symbol"] = data.__dict__["_raw"]["order"][
                "symbol"
            ]
            q_id = queue_id_hash[data.__dict__["_raw"]["symbol"]]
            queues[q_id].put(json.dumps(data.__dict__["_raw"]))

        except Exception as e:
            tlog(
                f"Exception in handle_trade_update(): exception of type {type(e).__name__} with args {e.args}"
            )

    await ws.subscribe(["trade_updates"])
    tlog("trade_run() completed")


async def run(
    symbols: List[str],
    data_ws: StreamConn,
    queues: List[Queue],
    queue_id_hash: Dict[str, int],
) -> None:
    data_channels = []
    for symbol in symbols:
        symbol_channels = [f"{OP}.{symbol}" for OP in config.WS_DATA_CHANNELS]
        data_channels += symbol_channels

    tlog(f"Watching {len(symbols)} symbols from Polygon.io")

    @data_ws.on(r"T$")
    async def handle_trade_event(conn, channel, data):
        try:
            if (time_diff := datetime.now(tz=timezone("America/New_York")) - data.timestamp) > timedelta(seconds=10):  # type: ignore
                tlog(f"T$ {data.symbol}: data out of sync {time_diff}")
                pass
            else:
                data.__dict__["_raw"]["EV"] = "T"
                q_id = queue_id_hash[data.__dict__["_raw"]["symbol"]]
                queues[q_id].put(json.dumps(data.__dict__["_raw"]))

                global last_msg_tstamp
                last_msg_tstamp = datetime.now()
        except Exception as e:
            tlog(
                f"Exception in handle_trade_event(): exception of type {type(e).__name__} with args {e.args}"
            )

    @data_ws.on(r"Q$")
    async def handle_quote_event(conn, channel, data):
        try:
            if (time_diff := datetime.now(tz=timezone("America/New_York")) - data.timestamp) > timedelta(seconds=10):  # type: ignore
                tlog(f"Q$ {data.symbol}: data out of sync {time_diff}")
                pass
            else:
                data.__dict__["_raw"]["EV"] = "Q"
                q_id = queue_id_hash[data.__dict__["_raw"]["symbol"]]
                queues[q_id].put(json.dumps(data.__dict__["_raw"]))

                global last_msg_tstamp
                last_msg_tstamp = datetime.now()
        except Exception as e:
            tlog(
                f"Exception in handle_quote_event(): exception of type {type(e).__name__} with args {e.args}"
            )

    @data_ws.on(r"A$")
    async def handle_second_bar(conn, channel, data):
        # print(f"A {data.__dict__['_raw']['symbol']}")
        try:
            if (time_diff := datetime.now(tz=timezone("America/New_York")) - data.start) > timedelta(seconds=8):  # type: ignore
                tlog(f"A$ {data.symbol}: data out of sync {time_diff}")
                pass
            else:
                data.__dict__["_raw"]["EV"] = "A"
                q_id = queue_id_hash[data.__dict__["_raw"]["symbol"]]
                queues[q_id].put(json.dumps(data.__dict__["_raw"]))

                global last_msg_tstamp
                last_msg_tstamp = datetime.now()
        except Exception as e:
            tlog(
                f"Exception in handle_second_bar(): exception of type {type(e).__name__} with args {e.args}"
            )

    @data_ws.on(r"AM$")
    async def handle_minute_bar(conn, channel, data):
        # print(f"AM {data.__dict__['_raw']['symbol']}")
        try:
            data.__dict__["_raw"]["EV"] = "AM"
            q_id = queue_id_hash[data.__dict__["_raw"]["symbol"]]
            queues[q_id].put(json.dumps(data.__dict__["_raw"]))

            global last_msg_tstamp
            last_msg_tstamp = datetime.now()
        except Exception as e:
            tlog(
                f"Exception in handle_minute_bar(): exception of type {type(e).__name__} with args {e.args}"
            )

    global last_msg_tstamp
    try:
        await data_ws.subscribe(data_channels)

        while True:
            # print(f"tick! {datetime.now() - last_msg_tstamp}")
            if (datetime.now() - last_msg_tstamp) > timedelta(
                seconds=config.polygon_seconds_timeout
            ):
                tlog(
                    f"no data activity since {last_msg_tstamp} attempting reconnect"
                )
                await data_ws.close(False)
                data_ws.data_ws = polygon.StreamConn(config.prod_api_key_id)
                await data_ws.data_ws.connect()
                data_ws.register(r"AM$", handle_minute_bar)
                data_ws.register(r"A$", handle_second_bar)
                data_ws.register(r"Q$", handle_quote_event)
                data_ws.register(r"T$", handle_trade_event)
                await data_ws.subscribe(data_channels)
                tlog("Polygon.io reconnected")
                last_msg_tstamp = datetime.now()
            await asyncio.sleep(config.polygon_seconds_timeout / 2)
    except asyncio.CancelledError:
        tlog("main Polygon.io consumer task cancelled ")
    except Exception as e:
        tlog(
            f"Exception in Polygon.io consumer task: exception of type {type(e).__name__} with args {e.args}"
        )
        traceback.print_exc()
    finally:
        tlog("main Polygon producer task completed ")


async def teardown_task(
    tz: DstTzInfo, ws: List[StreamConn], tasks: List[asyncio.Task]
) -> None:
    tlog("poylgon_producer teardown_task() starting")
    dt = datetime.today().astimezone(tz)
    to_market_close: timedelta
    try:
        to_market_close = (
            config.market_close - dt
            if config.market_close > dt
            else timedelta(hours=24) + (config.market_close - dt)
        )
        tlog(
            f"poylgon_producer tear-down task waiting for market close: {to_market_close}"
        )
    except Exception as e:
        tlog(
            f"poylgon_producer - exception of type {type(e).__name__} with args {e.args}"
        )
        return

    try:
        await asyncio.sleep(to_market_close.total_seconds() + 60 * 5)

        tlog("poylgon_producer teardown closing web-sockets")
        for w in ws:
            await w.close(False)

        tlog("poylgon_producer teardown closing tasks")

        for task in tasks:
            tlog(
                f"teardown_task(): requesting task {task.get_name()} to cancel"
            )
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                tlog("teardown_task(): task is cancelled now")

        # asyncio.get_running_loop().stop()

    except asyncio.CancelledError:
        tlog("teardown_task() cancelled during sleep")

    finally:
        tlog("teardown_task() done.")


"""
process main
"""


async def producer_async_main(
    queues: List[Queue], symbols: List[str], queue_id_hash: Dict[str, int]
):
    data_ws = tradeapi.StreamConn(
        base_url=config.prod_base_url,
        key_id=config.prod_api_key_id,
        secret_key=config.prod_api_secret,
        data_stream="polygon",
    )

    main_task = asyncio.create_task(
        run(
            symbols=symbols,
            data_ws=data_ws,
            queues=queues,
            queue_id_hash=queue_id_hash,
        ),
        name="main_task",
    )

    base_url = (
        config.prod_base_url if config.env == "PROD" else config.paper_base_url
    )
    api_key_id = (
        config.prod_api_key_id
        if config.env == "PROD"
        else config.paper_api_key_id
    )
    api_secret = (
        config.prod_api_secret
        if config.env == "PROD"
        else config.paper_api_secret
    )
    trade_ws = tradeapi.StreamConn(
        base_url=base_url, key_id=api_key_id, secret_key=api_secret,
    )

    trade_updates_task = asyncio.create_task(
        trade_run(ws=trade_ws, queues=queues, queue_id_hash=queue_id_hash),
        name="trade_updates_task",
    )

    tear_down = asyncio.create_task(
        teardown_task(
            timezone("America/New_York"), [data_ws, trade_ws], [main_task,],
        )
    )

    await asyncio.gather(
        main_task, trade_updates_task, tear_down, return_exceptions=True,
    )

    tlog("producer_async_main() completed")


def polygon_producer_main(
    queues: List[Queue],
    symbols: List[str],
    queue_id_hash: Dict[str, int],
    market_close: datetime,
) -> None:
    tlog(f"*** polygon_producer_main() starting w pid {os.getpid()} ***")
    try:
        config.market_close = market_close
        if not asyncio.get_event_loop().is_closed():
            asyncio.get_event_loop().close()
        asyncio.run(producer_async_main(queues, symbols, queue_id_hash))
        # loop = asyncio.new_event_loop()
        # asyncio.set_event_loop(asyncio.new_event_loop())
        # loop.run_until_complete(
        #    producer_async_main(queues, symbols, queue_id_hash)
        # )
        # loop.run_forever()
    except KeyboardInterrupt:
        tlog("producer_main() - Caught KeyboardInterrupt")
    except Exception as e:
        tlog(
            f"producer_main() - exception of type {type(e).__name__} with args {e.args}"
        )

    tlog("*** producer_main() completed ***")
