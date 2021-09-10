import json
import queue
import traceback
from datetime import date
from typing import Dict, List

import pandas as pd
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

    def get_symbols(self) -> List[Dict]:
        if not self.polygon_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")

        data = self.polygon_rest_client.stocks_equities_snapshot_all_tickers()
        return data.tickers

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
            symbol, 1, scale.name, start, end, unadjusted=False
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
        _df = pd.DataFrame.from_dict(
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
        _df["vwap"] = 0.0
        return _df


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
