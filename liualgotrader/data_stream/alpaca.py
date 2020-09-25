import asyncio
import json
from multiprocessing import Queue
from typing import Awaitable, Dict, List

import websockets

from liualgotrader.common import market_data
from liualgotrader.common.tlog import tlog

from ..common import config
from .streaming_base import StreamingBase, WSConnectState

NY = "America/New_York"


class AlpacaStreaming(StreamingBase):
    END_POINT = "wss://data.alpaca.markets/stream"

    def __init__(self, key: str, secret: str, queues: List[Queue]):
        self.key = key
        self.secret = secret
        self.state: WSConnectState = WSConnectState.NOT_CONNECTED
        self.websocket: websockets.client.WebSocketClientProtocol
        self.consumer_task: asyncio.Task
        self.stream_map: Dict = {}
        super().__init__(queues)

    async def connect(self) -> bool:
        """Connect web-socket and authenticate, update internal state"""
        try:
            self.websocket = await websockets.client.connect(self.END_POINT)
            self.state = WSConnectState.CONNECTED
        except websockets.WebSocketException as wse:
            tlog(f"Exception when connecting to Alpaca WS {wse}")
            self.state = WSConnectState.NOT_CONNECTED
            return False

        auth_payload = {
            "action": "authenticate",
            "data": {"key_id": self.key, "secret_key": self.secret},
        }
        await self.websocket.send(json.dumps(auth_payload))
        _greeting = await self.websocket.recv()

        if isinstance(_greeting, bytes):
            _greeting = _greeting.decode("utf-8")
        msg = json.loads(_greeting)
        if msg.get("data", {}).get("status") != "authorized":
            tlog(f"Invalid Alpaca API credentials, Failed to authenticate: {msg}")
            raise ValueError(
                f"Invalid Alpaca API credentials, Failed to authenticate: {msg}"
            )

        self.state = WSConnectState.AUTHENTICATED

        self.consumer_task = asyncio.create_task(
            self._consumer(), name="alpaca-streaming-consumer-task"
        )

        tlog("Successfully connected to Alpaca web-socket")
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

        _subscribe_payload = {
            "action": "listen",
            "data": {"streams": [f"alpacadatav1/AM.{symbol}"]},
        }
        await self.websocket.send(json.dumps(_subscribe_payload))

        q_id = int(
            list(market_data.minute_history.keys()).index(symbol)
            / config.num_consumer_processes_ratio
        )
        self.stream_map[symbol] = (handler, q_id)
        return True

    async def unsubscribe(self, symbol: str) -> bool:
        if self.state != WSConnectState.AUTHENTICATED:
            raise ValueError(
                f"{symbol} web-socket not ready for listening, make sure connect passed successfully"
            )

        _subscribe_payload = {
            "action": "unlisten",
            "data": {"streams": [f"alpacadatav1/AM.{symbol}"]},
        }
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
                stream = msg.get("stream")
                if stream != "listening":
                    try:
                        _func, _q_id = self.stream_map.get(stream[3:], None)
                        if _func:
                            await _func(stream, msg["data"], self.queues[_q_id])
                        else:
                            tlog(
                                f"{self.consumer_task.get_name()} received {_msg} to an unknown stream {stream}"
                            )
                    except Exception as e:
                        tlog(
                            f"{self.consumer_task.get_name()}  exception {e.__class__.__qualname__}:{e}"
                        )

        except websockets.WebSocketException as wse:
            tlog(f"{self.consumer_task.get_name()} received WebSocketException {wse}")
            await self._reconnect()
        except asyncio.CancelledError:
            tlog(f"{self.consumer_task.get_name()} cancelled")

        tlog(f"{self.consumer_task.get_name()} completed")

    @classmethod
    async def minutes_handler(cls, symbol: str, data: Dict, queue: Queue) -> None:
        if data["ev"] != "AM":
            tlog(
                f"AlpacaStreaming.minutes_handler() got invalid event data: {symbol}:{data}"
            )
            return

        if symbol[3:] != data["T"]:
            tlog(
                f"AlpacaStreaming.minutes_handler() symbol does not match data payload {symbol}:{data}"
            )
            return

        try:
            data["EV"] = "AM"
            data["open"] = data["o"]
            data["high"] = data["h"]
            data["low"] = data["l"]
            data["close"] = data["c"]
            data["volume"] = data["v"]
            data["vwap"] = data["vw"]
            data["average"] = data["a"]
            queue.put(json.dumps(data))
        except Exception as e:
            tlog(
                f"Exception in handle_minute_bar(): exception of type {type(e).__name__} with args {e.args}"
            )
