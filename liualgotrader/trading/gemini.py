import base64
import hashlib
import hmac
import json
import os
import queue
import ssl
import time
from datetime import date, datetime, timedelta
from threading import Thread
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import websocket
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.assets import get_asset_min_qty, round_asset
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import Order, QueueMapper, ThreadFlags, Trade
from liualgotrader.trading.base import Trader

utctz = timezone("UTC")


class GeminiTrader(Trader):
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_api_secret: Optional[str] = os.getenv("GEMINI_API_SECRET")
    base_url = "https://api.sandbox.gemini.com"
    base_websocket = "wss://api.sandbox.gemini.com"
    last_nonce = None

    def __init__(self, qm: QueueMapper = None):
        self.running_task: Optional[Thread] = None
        self.hb_task: Optional[Thread] = None
        self.send_hb = True
        self.ws = None
        self.flags: Optional[ThreadFlags] = None
        super().__init__(qm)

    @classmethod
    def _generate_request_headers(cls, payload: Dict) -> Dict:
        if not cls.gemini_api_secret or not cls.gemini_api_key:
            raise AssertionError(
                "both env variables GEMINI_API_KEY and GEMINI_API_SECRET must be set up"
            )
        t = datetime.now()
        payload_nonce = int(time.mktime(t.timetuple()) * 1000)

        if cls.last_nonce and cls.last_nonce == payload_nonce:
            payload_nonce += 1

        cls.last_nonce = payload_nonce

        payload["nonce"] = str(payload_nonce)
        encoded_payload = json.dumps(payload).encode()
        b64 = base64.b64encode(encoded_payload)
        signature = hmac.new(
            cls.gemini_api_secret.encode(), b64, hashlib.sha384
        ).hexdigest()

        return {
            "Content-Type": "text/plain",
            "Content-Length": "0",
            "X-GEMINI-APIKEY": cls.gemini_api_key,
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
    def _get_order_event_type(cls, order_data: Dict) -> Order.EventType:
        return (
            Order.EventType.canceled
            if order_data["is_cancelled"] == True
            else Order.EventType.fill
            if order_data["remaining_amount"] == "0"
            else Order.EventType.partial_fill
        )

    @classmethod
    def _get_trade_event_type(cls, trade_data: Dict) -> Order.EventType:
        return (
            Order.EventType.canceled
            if trade_data["type"] == "cancelled"
            else Order.EventType.rejected
            if trade_data["type"] == "rejected"
            else Order.EventType.canceled
            if trade_data["type"] == "cancel_rejected"
            else Order.EventType.fill
            if trade_data["remaining_amount"] == "0"
            else Order.EventType.partial_fill
        )

    @classmethod
    def _get_order_side(cls, order_data: Dict) -> Order.FillSide:
        return (
            Order.FillSide.buy
            if order_data["side"] == "buy"
            else Order.FillSide.sell
        )

    @classmethod
    def _order_from_dict(cls, order_data: Dict) -> Order:
        trades = order_data.get("trades", [])
        trade_fees: float = 0.0 + sum(float(t["fee_amount"]) for t in trades)
        return Order(
            order_id=order_data["order_id"],
            symbol=order_data["symbol"].lower(),
            filled_qty=float(order_data["executed_amount"]),
            event=cls._get_order_event_type(order_data),
            price=float(order_data["price"]),
            side=cls._get_order_side(order_data),
            submitted_at=pd.Timestamp(
                ts_input=order_data["timestampms"], unit="ms", tz="UTC"
            ),
            avg_execution_price=float(order_data["avg_execution_price"]),
            remaining_amount=float(order_data["remaining_amount"]),
            trade_fees=trade_fees,
        )

    @classmethod
    def _trade_from_dict(cls, trade_dict: Dict) -> Trade:
        tlog(f"GEMINI GOING TO SEND {trade_dict}")
        return Trade(
            order_id=trade_dict["order_id"],
            symbol=trade_dict["symbol"].lower(),
            event=cls._get_trade_event_type(trade_dict),
            filled_qty=float(trade_dict["fill"]["amount"])
            if "fill" in trade_dict
            else 0.0,
            trade_fee=float(
                trade_dict["fill"]["fee"] if "fill" in trade_dict else 0.0
            )
            if "fill" in trade_dict
            else 0.0,
            filled_avg_price=float(trade_dict["avg_execution_price"] or 0.0),
            liquidity=trade_dict["fill"]["liquidity"]
            if "fill" in trade_dict
            else "",
            updated_at=pd.Timestamp(
                ts_input=trade_dict["timestampms"], unit="ms", tz="UTC"
            ),
            side=Order.FillSide[trade_dict["side"]],
        )

    async def is_fractionable(self, symbol: str) -> bool:
        return True

    def check_error(self, result: Dict):
        if result.get("result") == "error":
            raise AssertionError(
                f"[EXCEPTION] {result['reason']}:{result['message']}"
            )

    async def is_order_completed(
        self, order_id: str, external_order_id: Optional[str] = None
    ) -> Tuple[
        Order.EventType, Optional[float], Optional[float], Optional[float]
    ]:
        order = await self.get_order(order_id)
        return (
            order.event,
            order.avg_execution_price,
            order.filled_qty,
            order.trade_fees,
        )

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        return datetime.now().replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=utctz
        ), datetime.now().replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=utctz
        )

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        return pd.DataFrame(
            index=pd.date_range(start=start_date, end=end_date)
        )

    def get_position(self, symbol: str) -> float:
        symbol = symbol.lower()
        endpoint = "/v1/balances"
        url = self.base_url + endpoint

        payload = {
            "request": endpoint,
        }
        headers = self._generate_request_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        if response.status_code == 200:
            return next(
                (
                    float(b["amount"])
                    for b in response.json()
                    if b["currency"] == symbol
                ),
                0.0,
            )

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
        return datetime.now().replace(
            hour=23, minute=59, second=59, microsecond=0, tzinfo=utctz
        ) - datetime.now().replace(tzinfo=utctz)

    async def reconnect(self):
        await self.close()
        await self.run()

    @classmethod
    def heartbeat(cls, flags: ThreadFlags):
        tlog("GEMINI HEARTBEAT thread starting")
        while flags.run:
            tlog("GEMINI HEARTBEAT")
            endpoint = "/v1/heartbeat"
            url = cls.base_url + endpoint

            payload = {
                "request": endpoint,
            }
            headers = cls._generate_request_headers(payload)
            response = requests.post(url, data=None, headers=headers)

            if response.status_code != 200:
                raise AssertionError(
                    f"HEARTHBEAT HTTP ERROR {response.status_code} {response.text}"
                )

            time.sleep(20)

        tlog("GEMINI HEARTBEAT thread terminated")

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
                symbol = trade.symbol.lower()
                tlog(f"GEMINI TRADING UPDATE:{trade}")
                to_send = {
                    "EV": "trade_update",
                    "symbol": symbol,
                    "trade": trade.__dict__,
                }
                try:
                    if qs := cls.get_instance().queues:
                        for q in qs.get_allqueues():
                            q.put(to_send, timeout=1)
                except queue.Full as f:
                    tlog(
                        f"[EXCEPTION] : queue for {symbol} is FULL:{f}, sleeping for 2 seconds and re-trying."
                    )
                    raise

    @classmethod
    def on_error(cls, ws, error):
        tlog(f"[ERROR] GeminiTrader {error}")

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
            self.flags = ThreadFlags(run=True)
            self.hb_task = Thread(target=self.heartbeat, args=(self.flags,))
            self.running_task.start()
            self.hb_task.start()

        return self.running_task

    async def close(self):
        if self.running_task and self.running_task.is_alive():
            tlog(f"close task {self.running_task}")
            self.ws.keep_running = False
            self.flags.run = False
            self.running_task.join()
            self.hb_task.join()
            tlog("task terminated")
            self.ws = None
            self.running_task = None
            self.hb_task = None
            self.flags = None

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

    async def cancel_order(self, order: Order) -> bool:
        endpoint = "/v1/order/cancel"
        url = self.base_url + endpoint

        payload = {"request": endpoint, "order_id": order.order_id}
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
        on_behalf_of: str = None,
    ) -> Order:
        symbol = symbol.lower()
        if order_type == "market":
            raise AssertionError(
                "GEMINI does not support market orders, use limit orders"
            )

        if qty < get_asset_min_qty(symbol):
            raise AssertionError(
                f"GEMINI requested quantity of {qty} is below minimum for {symbol}"
            )

        endpoint = "/v1/order/new"
        url = self.base_url + endpoint
        qty = round_asset(symbol, qty)
        payload = {
            "request": endpoint,
            "symbol": symbol,
            "amount": str(qty),
            "price": limit_price
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

        if self.flags:
            self.flags.run = False

        await self.close()

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )
