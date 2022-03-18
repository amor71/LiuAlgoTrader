import asyncio
import base64
import concurrent.futures
import hashlib
import hmac
import json
import os
import queue
import ssl
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from threading import Thread
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import pytz
import requests
import websocket

from liualgotrader.common import config
from liualgotrader.common.list_utils import chunks
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import (QueueMapper, TimeScale, Trade,
                                        WSEventType)
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI

utctz = pytz.timezone("UTC")


def requests_get(url):
    r = requests.get(url)

    if r.status_code in (429, 502):
        tlog(f"{url} return {r.status_code}, waiting and re-trying")
        time.sleep(10)
        return requests_get(url)

    return r


class GeminiData(DataAPI):
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_api_secret: Optional[str] = os.getenv("GEMINI_API_SECRET")
    base_url = "https://api.gemini.com"
    base_websocket = "wss://api.gemini.com"
    datapoints_per_request = 500
    max_trades_per_minute = 10

    def __init__(self):
        self.running_task: Optional[Thread] = None
        self.ws = None

    def get_symbols(self) -> List[str]:
        endpoint = "/v1/symbols"
        url = self.base_url + endpoint
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()

        raise AssertionError(
            f"HTTP ERROR {response.status_code} {response.text}"
        )

    def get_market_snapshot(self, filter_func) -> List[Dict]:
        raise NotImplementedError

    def _get_ranges(self, start, end):
        start_t = datetime.combine(start, datetime.min.time(), tzinfo=utctz)
        end_t = datetime.combine(end, datetime.max.time(), tzinfo=utctz)

        minutes = (end_t - start_t).total_seconds() / 60
        return pd.date_range(
            start_t,
            end_t,
            periods=minutes
            / (self.datapoints_per_request / self.max_trades_per_minute),
        )

    async def _consolidate_response(self, response, scale) -> pd.DataFrame:
        _df = pd.DataFrame(response.json())

        if _df.empty:
            return pd.DataFrame()

        _df = _df.set_index(_df.timestamp).sort_index()

        _df["s"] = pd.to_datetime(
            (_df.index * 1e9).astype("int64"),
            utc=True,
        )

        # _df.timestamp.apply(lambda x: pd.Timestamp(x, tz=utctz, unit="ns"))
        _df["amount"] = pd.to_numeric(_df.amount)
        _df["price"] = pd.to_numeric(_df.price)
        _df = _df[["s", "price", "amount"]].set_index("s")

        rule = "T" if scale == TimeScale.minute else "D"
        _newdf = _df.resample(rule).first()
        _newdf["high"] = _df.resample(rule).max().price
        _newdf["low"] = _df.resample(rule).min().price
        _newdf["close"] = _df.resample(rule).last().price
        _newdf["count"] = _df.resample(rule).count().amount
        _newdf["volume"] = _df.resample(rule).sum().amount
        _newdf = (
            _newdf.rename(columns={"price": "open", "s": "timestamp"})
            .drop(columns=["amount"])
            .sort_index()
        )
        _newdf = _newdf.dropna()
        _newdf["average"] = 0.0
        _newdf["vwap"] = 0.0

        return _newdf

    async def aget_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        symbol = symbol.lower()
        tlog(
            f"GEMINI start loading {symbol} from {start} to {end} w scale {scale}"
        )
        ranges = self._get_ranges(start, end)
        endpoint = f"/v1/trades/{symbol}"
        returned_df: pd.DataFrame = pd.DataFrame()
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            loop = asyncio.get_event_loop()
            futures = [
                loop.run_in_executor(
                    executor,
                    requests_get,
                    f"{self.base_url}{endpoint}?timestamp={int(current_timestamp.timestamp())}&limit_trades=500",
                )
                for current_timestamp in ranges[:-1]
            ]

            for response in await asyncio.gather(*futures):
                if response.status_code != 200:
                    raise ValueError(
                        f"HTTP ERROR {response.status_code} {response.text}"
                    )

                df = await self._consolidate_response(response, scale)

                if df.empty:
                    continue
                if returned_df.empty:
                    returned_df = df
                else:
                    returned_df = pd.concat([returned_df, df])
                    returned_df = returned_df[
                        ~returned_df.index.duplicated(keep="first")
                    ]

        tlog(
            f"GEMINI completed loading {symbol} from {start} to {end} w scale {scale}"
        )
        return returned_df

    def get_symbols_data(
        self,
        symbols: List[str],
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError(
            "get_symbols_data() not implemented yet for Gemini data provider"
        )

    def trading_days_slice(self, symbol: str, s: slice) -> slice:
        return s

    def get_last_trading(self, symbol: str) -> datetime:
        return datetime.now(timezone.utc)

    def get_trading_day(
        self, symbol: str, now: datetime, offset: int
    ) -> datetime:
        return (
            utctz.localize(datetime.combine(now, datetime.min.time()))
            if isinstance(now, date)
            else now
        ) + timedelta(days=offset)

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        symbol = symbol.lower()
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(
            self.aget_symbol_data(symbol, start, end, scale)
        )

    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_minutes")

    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_days")

    def get_max_data_points_per_load(self) -> int:
        raise NotImplementedError("get_max_data_points_per_load")


class GeminiStream(StreamingAPI):
    gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY")
    gemini_api_secret: Optional[str] = os.getenv("GEMINI_API_SECRET")
    base_url = "https://api.gemini.com"
    base_websocket = "wss://api.gemini.com"

    def __init__(self, queues: QueueMapper):
        self.running_task: Optional[Thread] = None
        self.ws = None
        super().__init__(queues)

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

    async def run(self):
        if not self.running_task:
            endpoint = "/v1/marketdata/btcusd"  # TODO need support all symbols in an efficient way
            payload = {"request": endpoint}
            headers = self._generate_ws_headers(payload)
            self.ws = websocket.WebSocketApp(
                f"{self.base_websocket}{endpoint}?trades=true&heartbeat=true",
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

    @classmethod
    def on_message(cls, ws, msgs):
        msg = json.loads(msgs)

        if msg["type"] != "update":
            return

        for event in msg["events"]:
            if event["type"] == "trade":
                cls.trades_handler(
                    pd.Timestamp(
                        datetime.fromtimestamp(msg["timestamp"]).astimezone(
                            utctz
                        )
                    ),
                    event,
                )

    @classmethod
    def on_error(cls, ws, error):
        tlog(f"[ERROR] GeminiStream {error}")

    @classmethod
    def on_close(cls, ws, close_status_code, close_msg):
        tlog(
            f"on_close(): GeminiStream status={close_status_code}, close_msg={close_msg}"
        )

    @classmethod
    def trades_handler(cls, timestamp: datetime, event: Dict):
        try:
            if (time_diff := (datetime.now(timezone.utc) - timestamp)) > timedelta(seconds=2):  # type: ignore
                # if randint(1, 100) == 1:  # nosec
                tlog(f"received a trade for btcusd out of sync w {time_diff}")

            event = {
                "symbol": "btcusd",
                "price": float(event["price"]),
                "open": float(event["price"]),
                "close": float(event["price"]),
                "high": float(event["price"]),
                "low": float(event["price"]),
                "timestamp": timestamp,
                "volume": float(event["amount"]),
                "exchange": "gemini",
                "conditions": event["makerSide"],
                "tape": "",
                "average": None,
                "count": 1,
                "vwap": None,
                "EV": "T",
            }

            cls.get_instance().queues["btcusd"].put(event, block=False)

        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {event['sym']} is FULL:{f}"
            )
            raise
        except AssertionError as e:
            tlog(f"[EXCEPTION] GEMINI process_message(): {e}")
            time.sleep(1)
            return
        except Exception as e:
            tlog(
                f"[EXCEPTION] process_message(): exception of type {type(e).__name__} with args {e.args}"
            )
            if config.debug_enabled:
                traceback.print_exc()

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        return True  # TODO Gemini - handle all symbols and event types
