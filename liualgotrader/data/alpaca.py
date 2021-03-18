import asyncio
import json
import queue
import traceback
from datetime import date, datetime, timedelta
from multiprocessing import Queue
from typing import Awaitable, Dict, List

import pandas as pd
import pytz
import websockets
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
            raise AssertionError("Must call w/ authenticated polygon client")

        data = self.alpaca_rest_client.list_assets()
        return data

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
            nytz.localize(
                datetime.now().replace(microsecond=0) - timedelta(days=1)
            ).isoformat()
            if end >= date.today()
            else end
        )
        print(_start, _end)
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        t: TimeFrame = (
            TimeFrame.Minute
            if scale == TimeScale.minute
            else TimeFrame.Day
            if scale == TimeScale.day
            else None
        )
        data = self.alpaca_rest_client.get_bars(
            symbol=symbol,
            timeframe=t,
            start=_start,
            end=_end,
            limit=10000,
            adjustment="raw",
        ).df
        if data.empty:
            raise ValueError(
                f"[ERROR] {symbol} has no data for {_start} to {_end} w {scale.name}"
            )

        return data


class AlpacaStream(StreamingAPI):
    def __init__(self, queues: QueueMapper):
        self.alpaca_ws_client = Stream(
            base_url=URL(config.alpaca_base_url),
            key_id=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
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
        print("msg:", msg)
        event = {}
        event["symbol"] = msg.symbol
        event["open"] = msg.open
        event["close"] = msg.close
        event["high"] = msg.high
        event["low"] = msg.low
        event["start"] = int(msg.timestamp // 1000000)
        event["volume"] = msg.volume
        event["count"] = 0.0
        event["vwap"] = 0.0
        event["average"] = 0.0
        event["totalvolume"] = None
        event["EV"] = "AM"

        try:
            print(event)
            cls.get_instance().queues[msg.symbol].put(event, timeout=1)
        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {event['sym']} is FULL:{f}, sleeping for 2 seconds and re-trying."
            )
            raise
        except Exception as e:
            tlog(
                f"[EXCEPTION] process_message(): exception of type {type(e).__name__} with args {e.args}"
            )
            traceback.print_exc()

    @classmethod
    async def trades_handler(cls, msg):
        print(f"trades_handler:{msg}")

    @classmethod
    async def quotes_handler(cls, msg):
        print(f"quotes_handler:{msg}")

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        print(symbols, events)
        for event in events:
            if event == WSEventType.SEC_AGG:
                tlog(f"event {event} not implemente in Alpaca")
            elif event == WSEventType.MIN_AGG:
                self.alpaca_ws_client.subscribe_bars(
                    AlpacaStream.bar_handler, *symbols
                )
            elif event == WSEventType.TRADE:
                self.alpaca_ws_client.subscribe_trades(
                    AlpacaStream.trades_handler, symbols
                )
            elif event == WSEventType.QUOTE:
                self.alpaca_ws_client.subscribe_quotes(
                    AlpacaStream.quotes_handler, symbols
                )
        return True
