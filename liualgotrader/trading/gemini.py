import asyncio
import base64
import hashlib
import hmac
import json
import os
import queue
import time
import traceback
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper
from liualgotrader.trading.base import Trader

nyc = timezone("America/New_York")


class GeminiTrader(Trader):
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_api_secret: Optional[str] = os.getenv("GEMINI_API_SECRET")
    base_url = "https://api.gemini.com"

    def __init__(self, qm: QueueMapper = None):
        if qm:
            ...
        self.running_task: Optional[asyncio.Task] = None
        super().__init__(qm)

    def generate_headers(self, payload: Dict) -> Dict:
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

    async def is_order_completed(self, order) -> Tuple[bool, float]:
        raise NotImplementedError("is_order_completed(")
        # return True, float(status.filled_avg_price)

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        raise NotImplementedError("is_order_completed(")

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        calendars = self.alpaca_rest_client.get_calendar(
            start=str(start_date), end=str(end_date)
        )
        _df = pd.DataFrame.from_dict([calendar._raw for calendar in calendars])
        _df["date"] = pd.to_datetime(_df.date)
        return _df.set_index("date")

    def get_position(self, symbol: str) -> float:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")
        pos = self.alpaca_rest_client.get_position(symbol)

        return float(pos.qty) if pos.side == "long" else -1.0 * float(pos.qty)

    async def get_order(self, order_id: str):
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")
        return self.alpaca_rest_client.get_order(order_id)

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

    async def run(self) -> Optional[asyncio.Task]:
        if not self.running_task:
            self.running_task = None
        return self.running_task

    async def close(self):
        if self.running_task:
            ...

    async def get_tradeable_symbols(self) -> List[str]:
        endpoint = "/v1/symbols"
        url = self.base_url + endpoint
        response = requests.get(url)
        symbols = response.json()
        print(symbols)
        return symbols

    async def get_shortable_symbols(self) -> List[str]:
        return []

    async def is_shortable(self, symbol) -> bool:
        return False

    async def cancel_order(self, order_id: str):
        endpoint = "/v1/order/cancel"
        url = self.base_url + endpoint

        payload = {"request": endpoint, "order_id": order_id}
        headers = self.generate_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        order_status = response.json()
        print(order_status)
        return order_status

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str,
        time_in_force: str,
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
            "price": str(limit_price) if order_type == "limit" else "10000000",
            "side": side,
            "type": "exchange limit",
            "client_order_id": client_order_id,
            "options": ["immediate-or-cancel"]
            if order_type == "market"
            else [],
        }
        headers = self.generate_headers(payload)
        response = requests.post(url, data=None, headers=headers)

        new_order = response.json()
        print(new_order)
        return new_order

    @classmethod
    async def trade_update_handler(cls, data):
        symbol = data.__dict__["_raw"]["order"]["symbol"]
        data.__dict__["_raw"]["EV"] = "trade_update"
        data.__dict__["_raw"]["symbol"] = symbol
        try:
            # cls.get_instance().queues[symbol].put(
            #    data.__dict__["_raw"], timeout=1
            # )
            for q in cls.get_instance().queues.get_allqueues():
                q.put(data.__dict__["_raw"], timeout=1)
        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {symbol} is FULL:{f}, sleeping for 2 seconds and re-trying."
            )
            raise
        # except AssertionError:
        #    for q in cls.get_instance().queues.get_allqueues():
        #        q.put(data.__dict__["_raw"], timeout=1)
        except Exception as e:
            tlog(f"[EXCEPTION] process_message(): exception {e}")
            if config.debug_enabled:
                traceback.print_exc()
