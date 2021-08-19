import asyncio
import json
import queue
import time
import traceback
from datetime import date, datetime, timedelta
from multiprocessing import Queue
from typing import Awaitable, Dict, List

import numpy as np
import pandas as pd
import pytz
from alpaca_trade_api.rest import REST, URL, TimeFrame
from alpaca_trade_api.stream import Stream

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import (QueueMapper, TimeScale, WSConnectState,
                                        WSEventType)
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI

NY = "America/New_York"
nytz = pytz.timezone(NY)


class AlpacaData(DataAPI):
    def __init__(self):
        self.alpaca_rest_client = REST(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )
        if not self.alpaca_rest_client:
            raise AssertionError(
                "Failed to authenticate Alpaca RESTful client"
            )

    def get_symbols(self) -> List[Dict]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        return self.alpaca_rest_client.list_assets()

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        _start = nytz.localize(
            datetime.combine(start, datetime.min.time())
        ).isoformat()
        _end = (
            nytz.localize(datetime.now().replace(microsecond=0)).isoformat()
            if end >= date.today()
            else end
        )
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        t: TimeFrame = (
            TimeFrame.Minute
            if scale == TimeScale.minute
            else TimeFrame.Day
            if scale == TimeScale.day
            else None
        )

        retry_count = 3
        while True:
            try:
                data = self.alpaca_rest_client.get_bars(
                    symbol=symbol,
                    timeframe=t,
                    start=_start,
                    end=_end,
                    limit=10000,
                    adjustment="raw",
                ).df
            except Exception as e:
                if not retry_count:
                    raise ValueError(
                        f"[ERROR] {symbol} has no data for {_start} to {_end} w {scale.name}"
                    )

                tlog(
                    f"[ERROR] failed to load {symbol} between {_start} and {_end}. Exception {type(e).__name__} with {e}. retrying"
                )
                time.sleep(10)
            else:
                break
            finally:
                retry_count -= 1
        data = data.tz_convert("America/New_York")

        if data.empty:
            raise ValueError(
                f"[ERROR] {symbol} has no data for {_start} to {_end} w {scale.name}"
            )

        data["average"] = data.vwap
        data["count"] = data.trade_count
        data["vwap"] = np.NaN

        return data[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "count",
                "average",
                "vwap",
            ]
        ]


class AlpacaStream(StreamingAPI):
    def __init__(self, queues: QueueMapper):
        self.alpaca_ws_client = Stream(
            base_url=URL(config.alpaca_base_url),
            key_id=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
            data_feed=config.alpaca_data_feed,
        )

        if not self.alpaca_ws_client:
            raise AssertionError(
                "Failed to authenticate Alpaca web_socket client"
            )

        self.running = False
        super().__init__(queues)

    async def run(self):
        if not self.running:
            if not self.queues:
                raise AssertionError(
                    "can't call `AlpacaStream.run()` without queues"
                )

            asyncio.create_task(self.alpaca_ws_client._run_forever())
            self.running = True

    @classmethod
    async def bar_handler(cls, msg):
        try:
            event = {
                "symbol": msg.symbol,
                "open": msg.open,
                "close": msg.close,
                "high": msg.high,
                "low": msg.low,
                "timestamp": pd.to_datetime(
                    msg.timestamp, utc=True
                ).astimezone(nytz),
                "volume": msg.volume,
                "count": msg.trade_count,
                "vwap": 0.0,
                "average": msg.vwap,
                "totalvolume": None,
                "EV": "AM",
            }
            cls.get_instance().queues[msg.symbol].put(event, timeout=1)
        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {event['sym']} is FULL:{f}"
            )
            raise
        except Exception as e:
            tlog(
                f"[EXCEPTION] process_message(): exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()

    @classmethod
    async def trades_handler(cls, msg):
        try:
            event = {
                "symbol": msg.symbol,
                "price": msg.price,
                "open": msg.price,
                "close": msg.price,
                "high": msg.price,
                "low": msg.price,
                "timestamp": pd.to_datetime(msg.timestamp),
                "volume": msg.size,
                "exchange": msg.exchange,
                "conditions": msg.conditions,
                "tape": msg.tape,
                "average": None,
                "count": 1,
                "vwap": None,
                "EV": "T",
            }

            cls.get_instance().queues[msg.symbol].put(event, timeout=1)
        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {event['sym']} is FULL:{f}"
            )
            raise
        except Exception as e:
            tlog(
                f"[EXCEPTION] process_message(): exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()

    @classmethod
    async def quotes_handler(cls, msg):
        print(f"quotes_handler:{msg}")

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        for event in events:
            if event == WSEventType.SEC_AGG:
                tlog(f"event {event} not implemented in Alpaca")
            elif event == WSEventType.MIN_AGG:
                self.alpaca_ws_client._data_ws._running = False
                self.alpaca_ws_client.subscribe_bars(
                    AlpacaStream.bar_handler, *symbols
                )
            elif event == WSEventType.TRADE:
                self.alpaca_ws_client.subscribe_trades(
                    AlpacaStream.trades_handler, *symbols
                )
            elif event == WSEventType.QUOTE:
                self.alpaca_ws_client.subscribe_quotes(
                    AlpacaStream.quotes_handler, *symbols
                )
        return True
