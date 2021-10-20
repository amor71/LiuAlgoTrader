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
from liualgotrader.common.types import Order, QueueMapper, Trade
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

    def _generate_request_headers(self, payload: Dict) -> Dict:
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

    def _generate_ws_headers(self, payload: Dict) -> Dict:
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

    @classmethod
    def _order_from_dict(cls, order_data: Dict) -> Order:
        return Order(
            order_id=order_data["order_id"],
            symbol=order_data["symbol"],
            filled_qty=float(order_data["executed_amount"]),
            event=Order.EventType.canceled
            if order_data["is_cancelled"] == True
            else Order.EventType.fill
            if order_data["remaining_amount"] == 0
            else Order.EventType.partial_fill,
            price=float(order_data["price"]),
            side=Order.FillSide.buy
            if order_data["side"] == "buy"
            else Order.FillSide.sell,
            submitted_at=pd.Timestamp(
                ts_input=order_data["timestampms"], unit="ms", tz="UTC"
            ),
            avg_execution_price=float(order_data["avg_execution_price"]),
            remaining_amount=float(order_data["remaining_amount"]),
        )

    @classmethod
    def _trade_from_dict(cls, trade_dict: Dict) -> Trade:
        return Trade(
            order_id=trade_dict["order_id"],
            symbol=trade_dict["symbol"],
            event=Order.EventType.canceled
            if trade_dict["type"] == "cancelled"
            else Order.EventType.rejected
            if trade_dict["type"] == "rejected"
            else Order.EventType.canceled
            if trade_dict["type"] == "cancel_rejected"
            else Order.EventType.fill
            if trade_dict["remaining_amount"] == "0"
            else Order.EventType.partial_fill,
            filled_qty=float(trade_dict["fill"]["amount"]),
            trade_fee=float(trade_dict["fill"]["fee"]),
            filled_avg_price=float(trade_dict["avg_execution_price"] or 0.0),
            liquidity=trade_dict["fill"]["liquidity"],
            updated_at=pd.Timestamp(
                ts_input=trade_dict["timestampms"], unit="ms", tz="UTC"
            ),
            side=Order.FillSide[trade_dict["side"]],
        )

    def check_error(self, result: Dict):
        if result.get("result") == "error":
            raise AssertionError(
                f"[EXCEPTION] {result['reason']}:{result['message']}"
            )

    async def is_order_completed(self, order: Order) -> Tuple[bool, float]:
        order = await self.get_order(order.order_id)
        return (
            (True, order.avg_execution_price)
            if order.remaining_amount == 0
            else (
                False,
                0.0,
            )
        )

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        return (
            datetime.today().replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
            datetime.today().replace(
                hour=23, minute=59, second=59, microsecond=0
            ),
        )

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        raise NotImplementedError("not relevant for Gemini Exchange")

    def get_position(self, symbol: str) -> float:
        endpoint = "/v1/balances"
        url = self.base_url + endpoint

        payload = {
            "request": endpoint,
        }
        headers = self._generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        if response.status_code == 200:
            for b in response.json():
                if b["currency"] == symbol:
                    return float(b["amount"])

            return 0.0

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )

    async def get_order(
        self, order_id: str, client_order_id: Optional[str] = None
    ) -> Order:
        endpoint = "/v1/order/status"
        url = self.base_url + endpoint

        payload = {
            "request": endpoint,
            "order_id": order_id,
            "include_trades": True,
        }
        headers = self._generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        if response.status_code == 200:
            order_data = response.json()
            self.check_error(order_data)

            return self._order_from_dict(order_data)

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )

    def is_market_open_today(self) -> bool:
        return True

    def get_time_market_close(self) -> Optional[timedelta]:
        return (
            datetime.today().replace(
                hour=23, minute=59, second=59, microsecond=0
            )
            - datetime.now()
        )

    async def reconnect(self):
        await self.close()
        await self.run()

    @classmethod
    def on_message(cls, ws, msgs):
        msgs = json.loads(msgs)
        if type(msgs) != list:
            return

        for msg in msgs:
            if msg["type"] in [
                "fill",
                "cancel_rejected",
                "cancelled",
                "rejected",
            ]:
                trade = cls._trade_from_dict(msg)
                tlog(f"GEMINI TRADING UPDATE:{trade}")
                to_send = {
                    "EV": "trade_update",
                    "symbol": "symbol",
                    "trade": trade.__dict__,
                }
                try:
                    qs = cls.get_instance().queues
                    if qs:
                        for q in qs.get_allqueues():
                            q.put(to_send, timeout=1)
                except queue.Full as f:
                    tlog(
                        f"[EXCEPTION] process_message(): queue for {symbol} is FULL:{f}, sleeping for 2 seconds and re-trying."
                    )
                    raise

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
            headers = self._generate_ws_headers(payload)
            self.ws = websocket.WebSocketApp(
                f"{self.base_websocket}{endpoint}?eventTypeFilter=cancel_rejected&eventTypeFilter=cancelled&eventTypeFilter=rejected&eventTypeFilter=fill&eventTypeFilter=closed&heartbeat=true",
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
            self.ws = None
            self.running_task = None

    async def get_tradeable_symbols(self) -> List[str]:
        endpoint = "/v1/symbols"
        url = self.base_url + endpoint
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )

    async def get_shortable_symbols(self) -> List[str]:
        return []

    async def is_shortable(self, symbol) -> bool:
        return False

    async def cancel_order(
        self, order_id: Optional[str] = None, order: Optional[Order] = None
    ):
        if order:
            _order_id = order.order_id
        elif order_id:
            _order_id = order_id
        else:
            raise AssertionError(
                "[ERROR] Gemini cancel_order() missing order details"
            )

        endpoint = "/v1/order/cancel"
        url = self.base_url + endpoint

        payload = {"request": endpoint, "order_id": _order_id}
        headers = self._generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)
        if response.status_code == 200:
            order_status = response.json()
            self.check_error(order_status)
            return order_status

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )

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
    ) -> Order:
        if order_type == "market":
            raise AssertionError(
                "GEMINI does not support market orders, use limit orders"
            )

        endpoint = "/v1/order/new"
        url = self.base_url + endpoint

        payload = {
            "request": endpoint,
            "symbol": symbol,
            "amount": str(qty),
            "price": str(limit_price)
            if order_type == "limit"
            else str(60000.0 * qty),
            "side": side,
            "type": "exchange limit",
            "client_order_id": client_order_id,
            "options": ["immediate-or-cancel"]
            if order_type == "market"
            else [],
        }
        headers = self._generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        if response.status_code == 200:
            new_order = response.json()
            self.check_error(new_order)
            return self._order_from_dict(new_order)

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )
