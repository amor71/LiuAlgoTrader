import asyncio
import base64
import hashlib
import hmac
import json
import os
import queue
import ssl
import time
import traceback
from datetime import date, datetime, timedelta
from threading import Thread
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import websocket
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper
from liualgotrader.trading.base import Trader

nyc = timezone("America/New_York")


class GeminiTrader(Trader):
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_api_secret: Optional[str] = os.getenv("GEMINI_API_SECRET")
    base_url = "https://api.sandbox.gemini.com"
    base_websocket = "wss://api.sandbox.gemini.com"

    def __init__(self, qm: QueueMapper = None):
        self.running_task: Optional[Thread] = None
        self.ws = None
        super().__init__(qm)

    def generate_request_headers(self, payload: Dict) -> Dict:
        if not self.gemini_api_secret or not self.gemini_api_key:
            raise AssertionError(
                "both env variables GEMINI_API_KEY and GEMINI_API_SECRET must be set up"
            )
        t = datetime.now()
        payload_nonce = str(int(time.mktime(t.timetuple()) * 1000))
        payload["nonce"] = payload_nonce
        encoded_payload = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded_payload)
        signature = hmac.new(
            self.gemini_api_secret.encode(), b64, hashlib.sha384
        ).hexdigest()

        return {
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "X-GEMINI-APIKEY": self.gemini_api_key,
            "X-GEMINI-PAYLOAD": b64,
            "X-GEMINI-SIGNATURE": signature,
            "Cache-Control": "no-cache",
        }

    def generate_ws_headers(self, payload: Dict) -> Dict:
        if not self.gemini_api_secret or not self.gemini_api_key:
            raise AssertionError(
                "both env variables GEMINI_API_KEY and GEMINI_API_SECRET must be set up"
            )
        t = datetime.now()
        payload_nonce = str(int(time.mktime(t.timetuple()) * 1000))
        payload["nonce"] = payload_nonce
        encoded_payload = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded_payload)
        signature = hmac.new(
            self.gemini_api_secret.encode(), b64, hashlib.sha384
        ).hexdigest()

        return {
            "X-GEMINI-APIKEY": self.gemini_api_key,
            "X-GEMINI-PAYLOAD": b64.decode(),
            "X-GEMINI-SIGNATURE": signature,
        }

    def check_error(self, result: Dict):
        if result.get("result") == "error":
            raise AssertionError(
                f"[EXCEPTION] {result['reason']}:{result['message']}"
            )

    async def is_order_completed(self, order) -> Tuple[bool, float]:
        order_status = await self.get_order(order["order_id"])
        self.check_error(order_status)
        return (
            (True, float(order_status["avg_execution_price"]))
            if float(order_status["executed_amount"])
            == float(order_status["original_amount"])
            else (
                False,
                0.0,
            )
        )

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        raise NotImplementedError("not relevant for Gemini Exchange")

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        raise NotImplementedError("not relevant for Gemini Exchange")

    def get_position(self, symbol: str) -> float:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")
        pos = self.alpaca_rest_client.get_position(symbol)

        return float(pos.qty) if pos.side == "long" else -1.0 * float(pos.qty)

    async def get_order(
        self, order_id: str, client_order_id: Optional[str] = None
    ):
        endpoint = "/v1/order/status"
        url = self.base_url + endpoint

        payload = {
            "request": endpoint,
            "order_id": order_id,
            "include_trades": True,
        }
        headers = self.generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        order_status = response.json()
        self.check_error(order_status)
        return order_status

    def is_market_open_today(self) -> bool:
        return True

    def get_time_market_close(self) -> Optional[timedelta]:
        return None

    async def reconnect(self):
        self.alpaca_rest_client = REST(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )
        if not self.alpaca_rest_client:
            raise AssertionError(
                "Failed to authenticate Alpaca RESTful client"
            )

    @classmethod
    def on_message(cls, ws, msg):
        tlog(f"{msg}")

    @classmethod
    def on_error(cls, ws, error):
        tlog(f"[ERROR] {error}")

    @classmethod
    def on_close(cls, ws, close_status_code, close_msg):
        tlog(f"on_close(): status={close_status_code}, close_msg={close_msg}")

    async def run(self):
        if not self.running_task:
            tlog("starting Gemini listener")

            endpoint = "/v1/order/events"
            payload = {"request": endpoint}
            headers = self.generate_ws_headers(payload)
            self.ws = websocket.WebSocketApp(
                f"{self.base_websocket}{endpoint}?eventTypeFilter=fill&eventTypeFilter=closed&heartbeat=trueheartbeat=true",
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                header=headers,
            )
            self.running_task = Thread(
                target=self.ws.run_forever,
                args=(None, {"cert_reqs": ssl.CERT_NONE}),
            )
            self.running_task.start()

        return self.running_task

    async def close(self):
        if self.running_task and self.running_task.is_alive():
            tlog(f"close task {self.running_task}")
            self.ws.keep_running = False
            self.running_task.join()
            tlog("task terminated")

    async def get_tradeable_symbols(self) -> List[str]:
        endpoint = "/v1/symbols"
        url = self.base_url + endpoint
        response = requests.get(url)
        return response.json()

    async def get_shortable_symbols(self) -> List[str]:
        return []

    async def is_shortable(self, symbol) -> bool:
        return False

    async def cancel_order(self, order_id: str):
        endpoint = "/v1/order/cancel"
        url = self.base_url + endpoint

        payload = {"request": endpoint, "order_id": order_id}
        headers = self.generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        order_status = response.json()
        self.check_error(order_status)
        return order_status

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str,
        time_in_force: str = None,
        limit_price: str = None,
        stop_price: str = None,
        client_order_id: str = None,
        extended_hours: bool = None,
        order_class: str = None,
        take_profit: dict = None,
        stop_loss: dict = None,
        trail_price: str = None,
        trail_percent: str = None,
    ):
        endpoint = "/v1/order/new"
        url = self.base_url + endpoint

        payload = {
            "request": endpoint,
            "symbol": symbol,
            "amount": str(qty),
            "price": str(limit_price) if order_type == "limit" else "40000",
            "side": side,
            "type": "exchange limit",
            "client_order_id": client_order_id,
            "options": ["immediate-or-cancel"]
            if order_type == "market"
            else [],
        }
        headers = self.generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        new_order = response.json()
        self.check_error(new_order)
        return new_order
