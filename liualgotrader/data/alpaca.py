import asyncio
import json
from datetime import date, datetime, timedelta
from multiprocessing import Queue
from typing import Awaitable, Dict, List

import pandas as pd
import websockets
from alpaca_trade_api.rest import REST, TimeFrame
from alpaca_trade_api.stream import Stream

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import TimeScale, WSConnectState, WSEventType
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import QueueMapper, StreamingAPI

NY = "America/New_York"


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
            symbol=symbol, timeframe=t, start=start, end=end, limit=10000
        ).df

        if data.empty:
            raise ValueError(
                f"[ERROR] {symbol} has no data for {start} to {end} w {scale.name}"
            )

        return data


class AlpacaStream(StreamingAPI):
    def __init__(self, queues: QueueMapper):
        self.alpaca_ws_client = Stream(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )

        if not self.alpaca_ws_client:
            raise AssertionError(
                "Failed to authenticate Alpaca web_socket client"
            )
        self.alpaca_ws_client.subscribe_trade_updates(
            AlpacaStream.trade_update_handler
        )
        self.alpaca_ws_client.run()

        super().__init__(queues)

    @classmethod
    async def trade_update_handler(cls, msg):
        print(f"trade_update_handler:{msg}")

    @classmethod
    async def bar_handler(cls, msg):
        print(f"bar_handler:{msg}")

    @classmethod
    async def trades_handler(cls, msg):
        print(f"trades_handler:{msg}")

    @classmethod
    async def quotes_handler(cls, msg):
        print(f"quotes_handler:{msg}")

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        for event in events:
            if event == WSEventType.SEC_AGG:
                raise NotImplementedError(
                    f"event {event} not implemente in Alpaca"
                )
            elif event == WSEventType.MIN_AGG:
                self.alpaca_ws_client.subscribe_bars(
                    AlpacaStream.bar_handler, symbols
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
