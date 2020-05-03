import json
from enum import Enum, auto

import websockets
from google.cloud import error_reporting

from common.tlog import tlog

error_logger = error_reporting.Client()


class WSConnectState(Enum):
    NOT_CONNECTED = auto()
    CONNECTED = auto()
    AUTHENTICATED = auto()


class AlpacaStreaming:
    END_POINT = "wss://data.alpaca.markets/stream"

    def __init__(self, key: str, secret: str):
        self.key = key
        self.secret = secret
        self.state: WSConnectState = WSConnectState.NOT_CONNECTED

    async def connect(self) -> bool:
        try:
            self.websocket = await websockets.connect(self.END_POINT)
            self.state = WSConnectState.CONNECTED
        except websockets.WebSocketException as wse:
            error_logger.report_exception()
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
            tlog(
                f"Invalid Alpaca API credentials, Failed to authenticate: {msg}"
            )
            return False

        self.state = WSConnectState.AUTHENTICATED
        return True
