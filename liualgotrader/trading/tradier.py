import asyncio
import json
import queue
import time as time_action
from datetime import date, datetime, time, timedelta
from threading import Thread
from typing import Dict, List, Optional, Tuple

import pandas as pd
import pytz
import requests
import websocket

from liualgotrader.common import config
from liualgotrader.common.assets import get_asset_min_qty, round_asset
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import Order, QueueMapper, ThreadFlags, Trade
from liualgotrader.trading.base import Trader

NY = "America/New_York"
nytz = pytz.timezone(NY)


class TradierTrader(Trader):
    order_symbol: Dict[int, str] = {}
    order_side: Dict[int, Order.FillSide] = {}

    def __init__(self, qm: QueueMapper = None):
        self.running_task: Optional[Thread] = None
        self.ws: Optional[websocket] = None
        self.ws_session_id: Optional[str] = None
        super().__init__(qm)

    def _get(self, url: str, params: Optional[Dict] = None):
        if params is None:
            params = {}
        r = requests.get(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {config.tradier_access_token}",
                "Accept": "application/json",
            },
        )
        if r.status_code in (429, 502):
            tlog(f"{r.url} return {r.status_code}, waiting and re-trying")
            time_action.sleep(10)
            return self._get(url, params)
        elif r.status_code != 200:
            raise ValueError(f"HTTP ERROR {r.url} {r.status_code} {r.text}")

        return r

    def _post(self, url: str, params: Optional[Dict] = None):
        if params is None:
            params = {}
        r = requests.post(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {config.tradier_access_token}",
                "Accept": "application/json",
            },
        )
        if r.status_code in (429, 502):
            tlog(f"{r.url} return {r.status_code}, waiting and re-trying")
            time_action.sleep(10)
            return self._post(url, params)
        elif r.status_code != 200:
            raise ValueError(f"HTTP ERROR {r.url} {r.status_code} {r.text}")

        return r

    def _delete(self, url: str, params: Optional[Dict] = None):
        if params is None:
            params = {}
        r = requests.delete(
            url,
            params=params,
            headers={
                "Authorization": f"Bearer {config.tradier_access_token}",
                "Accept": "application/json",
            },
        )
        if r.status_code in (429, 502):
            tlog(f"{r.url} return {r.status_code}, waiting and re-trying")
            time_action.sleep(10)
            return self._delete(url, params)
        elif r.status_code != 200:
            raise ValueError(f"HTTP ERROR {r.url} {r.status_code} {r.text}")

        return r

    async def is_fractionable(self, symbol: str) -> bool:
        return False

    async def is_order_completed(
        self, order_id: str, external_order_id: Optional[str] = None
    ) -> Tuple[Order.EventType, float, float, float]:
        order = await self.get_order(order_id, external_order_id)
        return (
            order.event,
            float(order.avg_execution_price or 0.0),
            float(order.filled_qty or 0.0),
            0.0,
        )

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        url = f"{config.tradier_base_url}markets/clock"
        response = self._get(
            url,
        )
        data = response.json()

        last_open_date = datetime.strptime(
            data["clock"]["date"], "%Y-%m-%d"
        ).date()
        if last_open_date == date.today():
            start: Optional[datetime] = nytz.localize(
                datetime.combine(
                    date=last_open_date,
                    time=time(hour=7, minute=0, second=0, microsecond=0),
                )
            )

            end: Optional[datetime] = nytz.localize(
                datetime.combine(
                    date=last_open_date,
                    time=time(
                        hour=19, minute=55, second=59, microsecond=999999
                    ),
                )
            )
        else:
            start = end = None

        return start, end

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        url = f"{config.tradier_base_url}markets/calendar"
        d = start_date
        df = pd.DataFrame()

        while True:
            response = self._get(
                url, params={"month": d.month, "year": d.year}
            )

            data = response.json()["calendar"]["days"]["day"]
            dict_data: Dict = {
                element["date"]: element
                for element in data
                if element["status"] == "open"
            }
            df1 = pd.DataFrame.from_dict(dict_data, orient="index")
            df1["close"] = df1.apply(
                lambda x: x.get("postmarket", x["open"])["end"], axis=1
            )
            df1["open"] = df1.apply(lambda x: x["premarket"]["start"], axis=1)

            df1.index = pd.to_datetime(df1.index)
            df1 = df1[["open", "close"]].loc[
                (datetime.combine(start_date, time.min) <= df1.index)
                & (df1.index <= datetime.combine(end_date, time.min))
            ]
            df = pd.concat([df, df1])
            if d.month == end_date.month and d.year == end_date.year:
                break

            try:
                d = date(month=d.month + 1, day=d.day, year=d.year)
            except ValueError:
                d = date(month=d.month + 1, day=d.day - 1, year=d.year)

        return df

    def get_position(self, symbol: str) -> float:
        url = f"{config.tradier_base_url}accounts/{config.tradier_account_number}/positions"
        response = self._get(
            url,
        )
        data = response.json()
        if data["positions"] == "null":
            return 0.0

        data = data["positions"]["position"]
        if isinstance(data, dict):
            return data["quantity"] if data["symbol"] == symbol else 0.0

        return next(
            (
                position["quantity"]
                for position in data
                if position["symbol"] == symbol
            ),
            0.0,
        )

    @classmethod
    def _get_event(cls, order_event: str) -> Order.EventType:
        return (
            Order.EventType.fill
            if order_event == "filled"
            else Order.EventType.partial_fill
            if order_event == "partially_filled"
            else Order.EventType.canceled
            if order_event == "canceled"
            else Order.EventType.rejected
            if order_event == "rejected"
            else Order.EventType.pending
            if order_event == "pending"
            else Order.EventType.error
            if order_event == "error"
            else Order.EventType.open
            if order_event == "open"
            else Order.EventType.other
        )

    async def get_order(
        self, order_id: str, client_order_id: Optional[str] = None
    ) -> Order:
        url = f"{config.tradier_base_url}accounts/{config.tradier_account_number}/orders/{order_id}"
        response = self._get(
            url,
        )
        data = response.json()
        return Order(
            order_id=data["order"]["id"],
            symbol=data["order"]["symbol"],
            event=self._get_event(data["order"]["status"]),
            submitted_at=data["order"]["create_date"],
            price=data["order"]["last_fill_price"],
            trade_fees=0.0,
            filled_qty=data["order"]["exec_quantity"],
            side=self._get_event_side(data["order"]["side"]),
            remaining_amount=data["order"]["remaining_quantity"],
            avg_execution_price=data["order"]["avg_fill_price"],
            external_account_id=data["order"]["tag"]
            if "tag" in data["order"]
            else None,
        )

    def is_market_open_today(self) -> bool:
        url = f"{config.tradier_base_url}markets/calendar"
        response = self._get(
            url,
        )
        data = response.json()
        today = str(datetime.now(nytz).date())
        return next(
            (
                day["status"] == "open"
                for day in data["calendar"]["days"]["day"]
                if day["date"] == today
            ),
            False,
        )

    def get_time_market_close(self) -> Optional[timedelta]:
        url = f"{config.tradier_base_url}markets/calendar"
        response = self._get(
            url,
        )
        data = response.json()
        today = str(datetime.now(nytz).date())
        return next(
            (
                day.get("postmarket", day["open"])["end"]
                for day in data["calendar"]["days"]["day"]
                if day["date"] == today and "open" in day
            ),
            None,
        )

    async def get_tradeable_symbols(self) -> List[str]:
        return await self.get_shortable_symbols()

    async def get_shortable_symbols(self) -> List[str]:
        url = f"{config.tradier_base_url}markets/etb"
        response = self._get(
            url,
        )
        data = response.json()
        return [
            security["symbol"]
            for security in data["securities"]["security"]
            if security["type"] == "stock"
        ]

    async def is_shortable(self, symbol) -> bool:
        return symbol.upper() in await self.get_shortable_symbols()

    async def cancel_order(self, order: Order) -> bool:
        url = f"{config.tradier_base_url}accounts/{config.tradier_account_number}/orders/{order.order_id}"

        response = self._delete(
            url,
        )
        data = response.json()
        return data["order"]["status"] == "ok"

    @classmethod
    def _get_event_side(cls, side: str) -> Order.FillSide:
        if side in {"buy", "buy_to_cover"}:
            return Order.FillSide.buy

        return Order.FillSide.sell

    async def subscribe_order_status_update(self) -> None:
        if (
            self.ws is not None
            and self.ws_session_id
            and self.running_task
            and self.running_task.is_alive()
        ):
            payload = {
                "events": ["order"],
                "sessionid": self.ws_session_id,
                "excludeAccounts": [],
            }
            self.ws.send(json.dumps(payload))
            tlog(
                f"subscribed for order update on session {self.ws_session_id}"
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
        url = f"{config.tradier_base_url}accounts/{config.tradier_account_number}/orders"

        params: Dict = {
            "class": "equity",
            "symbol": symbol,
            "side": side,
            "quantity": str(int(qty)),
            "duration": "day",
            "type": order_type,
        }

        if limit_price:
            params["price"] = str(round(float(limit_price), 2))
        if stop_price:
            params["stop"] = str(round(float(stop_price), 2))
        if on_behalf_of:
            params["tag"] = on_behalf_of

        response = self._post(
            url,
            params,
        )
        data = response.json()

        if "errors" in data:
            raise ValueError(f"order failed with {data['errors']}")

        event_side = self._get_event_side(side)
        o = Order(
            symbol=symbol,
            order_id=data["order"]["id"],
            event=Order.EventType.pending,
            side=event_side,
            submitted_at=datetime.now(nytz),
            remaining_amount=qty,
        )

        if on_behalf_of:
            o.external_account_id = on_behalf_of
        if limit_price:
            o.price = float(limit_price)

        TradierTrader.order_symbol[int(o.order_id)] = symbol
        TradierTrader.order_side[int(o.order_id)] = event_side
        return o

    async def reconnect(self):
        await self.close()
        await self.run()

    async def run(self) -> Optional[asyncio.Task]:
        if not self.running_task:
            tlog("starting Tradier Account listener")

            url = f"{config.tradier_base_url}accounts/events/session"

            response = self._post(
                url,
            )
            data = response.json()

            ws_url = data["stream"]["url"]
            self.ws_session_id = data["stream"]["sessionid"]

            tlog(
                f"starting WebSocketApp on {ws_url} with session-id {self.ws_session_id}"
            )
            self.ws = websocket.WebSocketApp(
                ws_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
            )
            self.running_task = Thread(
                target=self.ws.run_forever,
            )
            self.running_task.start()
            await asyncio.sleep(1.0)
            await self.subscribe_order_status_update()

        return self.running_task  # type: ignore

    async def close(self):
        if self.running_task and self.running_task.is_alive():
            tlog(f"close task {self.running_task}")
            self.ws.keep_running = False
            self.running_task.join()
            tlog("task terminated")
            self.ws = None
            self.running_task = None
            self.ws_session_id = None

    @classmethod
    def _trade_from_dict(cls, trade_dict: Dict) -> Trade:
        return Trade(
            order_id=trade_dict["id"],
            symbol=TradierTrader.order_symbol[trade_dict["id"]],
            event=cls._get_event(trade_dict["status"]),
            side=TradierTrader.order_side[trade_dict["id"]],
            filled_qty=float(trade_dict.get("last_fill_quantity", 0.0)),
            trade_fee=0.0,
            filled_avg_price=float(trade_dict.get("last_fill_price", 0.0)),
            liquidity="",
            updated_at=trade_dict["create_date"],
        )

    @classmethod
    def on_message(cls, ws, msgs):
        msg = json.loads(msgs)

        if msg["event"] != "order":
            return

        if (
            msg["status"]
            in {
                "filled",
                "cancel_rejected",
                "cancelled",
                "rejected",
            }
            and msg["id"] in TradierTrader.order_symbol
        ):
            trade = cls._trade_from_dict(msg)
            symbol = trade.symbol.lower()
            tlog(f"TRADIER TRADING UPDATE:{trade}")
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
                    f"[EXCEPTION] queue for {symbol} is FULL:{f}, sleeping for 2 seconds and re-trying."
                )
                raise

    @classmethod
    def on_error(cls, ws, error):
        tlog(f"[ERROR] TradierTrader {error}")

    @classmethod
    def on_close(cls, ws, close_status_code, close_msg):
        tlog(
            f"on_close(): TradierTrader status={close_status_code}, close_msg={close_msg}"
        )
