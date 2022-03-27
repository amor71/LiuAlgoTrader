import json
import queue
import traceback
from datetime import date, datetime
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd
import requests
from polygon import STOCKS_CLUSTER, RESTClient, WebSocketClient

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper, TimeScale, WSEventType
from liualgotrader.data.data_base import DataAPI
from liualgotrader.data.streaming_base import StreamingAPI


class PolygonData(DataAPI):
    def __init__(self):
        self.polygon_rest_client = RESTClient(config.polygon_api_key)
        if not self.polygon_rest_client:
            raise AssertionError(
                "Failed to authenticate Polygon restful client"
            )

    def get_market_snapshot(
        self, filter_func: Optional[Callable]
    ) -> List[Dict]:
        if not self.polygon_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")
        # this API endpoint requires at least starter subscriptions from Polygon
        data = self.polygon_rest_client.stocks_equities_snapshot_all_tickers()
        return (
            list(filter(filter_func, data.tickers))
            if filter_func is not None
            else data.tickers
        )

    def get_symbols(self) -> List[str]:
        if not self.polygon_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")
        # parse symbols on the first page
        data = self.polygon_rest_client.reference_tickers_v3(
            limit=1000, active=True
        )
        # use set to deduplicate in case paginated response return duplicate symbols
        symbols = {d["ticker"] for d in data.results}
        next_url = f"{data.next_url}&apiKey={config.polygon_api_key}"
        # parse the pagination
        while True:
            response = requests.get(next_url).json()
            if "next_url" not in response:
                break
            symbols.update([d["ticker"] for d in response["results"]])
            next_url = (
                f"{response['next_url']}&apiKey={config.polygon_api_key}"
            )
        return list(symbols)

    def get_symbol_data(
        self,
        symbol: str,
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> pd.DataFrame:
        if not self.polygon_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")

        data = self.polygon_rest_client.stocks_equities_aggregates(
            symbol, 1, scale.name, start, end, unadjusted=False, limit=50000
        )
        if not data or not hasattr(data, "results"):
            raise ValueError(
                f"[ERROR] {symbol} has no data for {start} to {end} w {scale.name}"
            )

        d = {
            pd.Timestamp(result["t"], unit="ms", tz="America/New_York"): [
                result.get("o"),
                result.get("h"),
                result.get("l"),
                result.get("c"),
                result.get("v"),
                result.get("vw"),
                result.get("n"),
            ]
            for result in data.results
        }
        df = pd.DataFrame.from_dict(
            d,
            orient="index",
            columns=[
                "open",
                "high",
                "low",
                "close",
                "volume",
                "average",
                "count",
            ],
        )
        df["vwap"] = np.NaN
        return df

    def get_symbols_data(
        self,
        symbols: List[str],
        start: date,
        end: date = date.today(),
        scale: TimeScale = TimeScale.minute,
    ) -> Dict[str, pd.DataFrame]:
        raise NotImplementedError("get_symbols_data")

    def get_last_trading(self, symbol: str) -> datetime:
        snapshot_data = (
            self.polygon_rest_client.stocks_equities_snapshot_single_ticker(
                symbol
            )
        )
        return pd.Timestamp(
            snapshot_data.ticker.last_trade.timestamp_of_this_trade,
            unit="ns",
            tz="America/New_York",
        )

    def get_trading_day(
        self, symbol: str, now: datetime, offset: int
    ) -> datetime:
        raise NotImplementedError("get_trading_day")

    def trading_days_slice(self, symbol: str, slice) -> slice:
        raise NotImplementedError("trading_days_slice")

    def num_trading_minutes(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_minutes")

    def num_trading_days(self, symbol: str, start: date, end: date) -> int:
        raise NotImplementedError("num_trading_days")

    def get_max_data_points_per_load(self) -> int:
        raise NotImplementedError("get_max_data_points_per_load")


class PolygonStream(StreamingAPI):
    def __init__(self, queues: QueueMapper):
        self.polygon_ws_client = WebSocketClient(
            cluster=STOCKS_CLUSTER,
            auth_key=config.polygon_api_key,
            process_message=PolygonStream.process_message,
            on_close=PolygonStream.on_close,
            on_error=PolygonStream.on_error,
        )
        if not self.polygon_ws_client:
            raise AssertionError(
                "Failed to authenticate Polygon web_socket client"
            )
        self.polygon_ws_client.run_async()
        super().__init__(queues)

    async def subscribe(
        self, symbols: List[str], events: List[WSEventType]
    ) -> bool:
        args = []
        for symbol in symbols:
            for event in events:
                if event == WSEventType.SEC_AGG:
                    action = "A"
                elif event == WSEventType.MIN_AGG:
                    action = "AM"
                elif event == WSEventType.TRADE:
                    action = "T"
                elif event == WSEventType.QUOTE:
                    action = "Q"

                args.append(f"{action}.{symbol}")

        tlog(f"subscribe(): adding subscription {args}")
        self.polygon_ws_client.subscribe(*args)

        return True

    async def run(self):
        pass

    async def unsubscribe(self, symbol: str) -> bool:
        raise NotImplementedError("not implemented yet")

    async def close(
        self,
    ) -> None:
        self.polygon_ws_client.close_connection()

    @classmethod
    def handle_event(cls, event: Dict):
        print("event:", event)
        try:
            event["EV"] = event["ev"]
            if "s" in event:
                event["start"] = event["s"]
            if "o" in event:
                event["open"] = event["o"]
            if "h" in event:
                event["high"] = event["h"]
            if "l" in event:
                event["low"] = event["l"]
            if "c" in event:
                event["close"] = event["c"]
            if "v" in event:
                event["volume"] = event["v"]
            if "vw" in event:
                event["vwap"] = event["vw"]
            if "a" in event:
                event["average"] = event["a"]
            if "av" in event:
                event["totalvolume"] = event["av"]
            if "sym" in event:
                event["symbol"] = event["sym"]
            if "z" in event:
                event["count"] = event["z"]
            cls.get_instance().queues[event["sym"]].put(event, timeout=1)
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
    def process_message(cls, message):
        payload = json.loads(message)
        for event in payload:
            if event["ev"] in ("A", "AM", "T", "Q"):
                cls.handle_event(event)

    @classmethod
    def on_error(cls, ws, error):
        tlog(f"[ERROR] on_error(): {error}")

    @classmethod
    def on_close(cls, ws, close_status_code, close_msg):
        tlog(f"[INFO] on_close() called with {close_status_code, close_msg}")
