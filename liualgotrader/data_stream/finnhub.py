import asyncio
import json
from datetime import datetime, timedelta
from multiprocessing import Queue
from typing import Awaitable, Dict, List

import pandas as pd
import websockets
from pytz import timezone

from liualgotrader.common import market_data
from liualgotrader.common.tlog import tlog

from .streaming_base import StreamingBase, WSConnectState

NY = "America/New_York"


class FinnhubStreaming(StreamingBase):
    END_POINT = "wss://ws.finnhub.io?token="

    def __init__(
        self, api_key: str, queues: List[Queue], queue_id_hash: Dict[str, int]
    ):
        self.api_key = api_key
        self.state: WSConnectState = WSConnectState.NOT_CONNECTED
        self.websocket: websockets.client.WebSocketClientProtocol
        self.consumer_task: asyncio.Task
        self.queue_id_hash = queue_id_hash
        self.stream_map: Dict = {}
        self.ohlc: Dict[str, List] = {}
        super().__init__(queues)

    async def connect(self) -> bool:
        """Connect web-socket and authenticate, update internal state"""
        try:
            url = f"{self.END_POINT}{self.api_key}"
            tlog(f"FinnhubStreaming - setting up web-socket for {url}")
            self.websocket = await websockets.client.connect(url)
            self.state = WSConnectState.CONNECTED
        except websockets.WebSocketException as wse:
            tlog(f"Exception when connecting to Finnhub WS {wse}")
            self.state = WSConnectState.NOT_CONNECTED
            return False
        else:
            tlog("FinnhubStreaming - web-socket created successfully")
        self.state = WSConnectState.AUTHENTICATED

        self.consumer_task = asyncio.create_task(
            self._consumer(), name="finnhub-streaming-consumer-task"
        )

        tlog("Successfully connected to Finnhub web-socket")
        return True

    async def close(self) -> None:
        """Close open websocket, if open"""
        if self.state not in (
            WSConnectState.AUTHENTICATED,
            WSConnectState.CONNECTED,
        ):
            raise ValueError("can't close a non-open connection")
        try:
            await self.websocket.close()
        except websockets.WebSocketException as wse:
            tlog(f"failed to close web-socket w exception {wse}")

        self.state = WSConnectState.NOT_CONNECTED

    async def subscribe(self, symbol: str, handler: Awaitable) -> bool:
        if self.state != WSConnectState.AUTHENTICATED:
            raise ValueError(
                f"{symbol} web-socket not ready for listening, make sure connect passed successfully"
            )
        _subscribe_payload = {"type": "subscribe", "symbol": f"{symbol}"}
        await self.websocket.send(json.dumps(_subscribe_payload))
        self.stream_map[symbol] = (handler, self.queue_id_hash[symbol])
        return True

    async def unsubscribe(self, symbol: str) -> bool:
        if self.state != WSConnectState.AUTHENTICATED:
            raise ValueError(
                f"{symbol} web-socket not ready for listening, make sure connect passed successfully"
            )
        _subscribe_payload = {"type": "unsubscribe", "symbol": f"{symbol}"}
        await self.websocket.send(json.dumps(_subscribe_payload))
        self.stream_map.pop(symbol, None)
        return False

    async def _reconnect(self) -> None:
        """automatically reconnect socket, and re-subscribe, internal"""
        tlog(f"{self.consumer_task.get_name()} reconnecting")
        await self.close()
        if await self.connect():
            _dict = self.stream_map.copy()
            self.stream_map.clear()

            for symbol in _dict:
                await self.subscribe(symbol, _dict[symbol])
        else:
            tlog(
                f"{self.consumer_task.get_name()} failed reconnect check log for reason"
            )

    async def _consumer(self) -> None:
        """Main tread loop for consuming incoming messages, internal only """

        tlog(f"{self.consumer_task.get_name()} starting")
        try:
            while True:
                _msg = await self.websocket.recv()
                if isinstance(_msg, bytes):
                    _msg = _msg.decode("utf-8")
                msg = json.loads(_msg)

                event = msg.get("type")
                if event == "ping":
                    continue
                elif event == "trade":
                    stream = msg.get("data", None)
                    for item in stream:
                        try:
                            symbol = item["s"]
                            price = item["p"]
                            volume = item["v"]
                            start = pd.Timestamp(item["t"], tz=NY, unit="ms")
                            time_diff = (
                                datetime.now(tz=timezone("America/New_York")) - start
                            )
                            if time_diff > timedelta(seconds=6):  # type: ignore
                                tlog(f"{symbol}: data out of sync {time_diff}")
                                continue
                            _func, _q_id = self.stream_map.get(symbol, None)

                            minute = start.replace(second=0, microsecond=0)
                            if symbol not in self.ohlc or self.ohlc[symbol][0] < minute:
                                self.ohlc[symbol] = [
                                    minute,
                                    price,
                                    price,
                                    price,
                                    price,
                                    volume,
                                ]
                            else:
                                self.ohlc[symbol] = [
                                    minute,
                                    self.ohlc[symbol][1],
                                    max(price, self.ohlc[symbol][2]),
                                    min(price, self.ohlc[symbol][3]),
                                    price,
                                    self.ohlc[symbol][5] + volume,
                                ]

                            if symbol not in market_data.volume_today:
                                market_data.volume_today[symbol] = 0
                            market_data.volume_today[symbol] += volume

                            if _func:
                                await _func(
                                    symbol,
                                    item["t"],
                                    self.ohlc[symbol],
                                    self.queues[_q_id],
                                )
                            else:
                                tlog(
                                    f"{self.consumer_task.get_name()} received {_msg} to an unknown stream {stream}"
                                )
                        except Exception as e:
                            tlog(
                                f"{self.consumer_task.get_name()}  exception {e.__class__.__qualname__}:{e}"
                            )
                elif event == "error":
                    tlog(f"{self.consumer_task.get_name()} [ERROR] {msg}")
                else:
                    tlog(
                        f"{self.consumer_task.get_name()} [ERROR] unknown event-type {event} ({msg})"
                    )
        except websockets.WebSocketException as wse:
            tlog(f"{self.consumer_task.get_name()} received WebSocketException {wse}")
            await self._reconnect()
        except asyncio.CancelledError:
            tlog(f"{self.consumer_task.get_name()} cancelled")
        except Exception as e:
            tlog(
                f"{self.consumer_task.get_name()}  exception {e.__class__.__qualname__}:{e}"
            )

        tlog(f"{self.consumer_task.get_name()} completed")

    @classmethod
    async def handler(cls, symbol: str, when: int, data: List, queue: Queue) -> None:
        payload = {
            "EV": "A",
            "symbol": symbol,
            "open": data[1],
            "high": data[2],
            "low": data[3],
            "close": data[4],
            "volume": data[5],
            "vwap": None,
            "average": None,
            "start": when,
            "totalvolume": market_data.volume_today[symbol],
        }
        queue.put(json.dumps(payload))
