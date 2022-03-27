import asyncio
import os
import queue
import time
import traceback
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from alpaca_trade_api.entity import Order as AlpacaOrder
from alpaca_trade_api.rest import REST, URL, Entity
from alpaca_trade_api.stream import Stream
from pytz import timezone
from requests.auth import HTTPBasicAuth

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import Order, QueueMapper, Trade
from liualgotrader.trading.base import Trader

nyc = timezone("America/New_York")


class AlpacaTrader(Trader):
    def __init__(self, qm: QueueMapper = None):
        self.market_open: Optional[datetime]
        self.market_close: Optional[datetime]
        self.alpaca_brokage_api_baseurl = os.getenv(
            "ALPACA_BROKER_API_BASEURL", None
        )
        self.alpaca_brokage_api_key = os.getenv("ALPACA_BROKER_API_KEY", None)
        self.alpaca_brokage_api_secret = os.getenv(
            "ALPACA_BROKER_API_SECRET", None
        )

        self.alpaca_rest_client = REST(
            base_url=URL(config.alpaca_base_url),
            key_id=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
        )
        if qm:
            self.alpaca_ws_client = Stream(
                base_url=URL(config.alpaca_base_url),
                key_id=config.alpaca_api_key,
                secret_key=config.alpaca_api_secret,
            )
            if not self.alpaca_ws_client:
                raise AssertionError(
                    "Failed to authenticate Alpaca web_socket client"
                )
            self.alpaca_ws_client.subscribe_trade_updates(
                AlpacaTrader.trade_update_handler
            )
        self.running_task: Optional[asyncio.Task] = None

        now = datetime.now(nyc)
        calendar = self.alpaca_rest_client.get_calendar(
            start=now.strftime("%Y-%m-%d"), end=now.strftime("%Y-%m-%d")
        )[0]

        if now.date() >= calendar.date.date():
            self.market_open = now.replace(
                hour=calendar.open.hour,
                minute=calendar.open.minute,
                second=0,
                microsecond=0,
            )
            self.market_close = now.replace(
                hour=calendar.close.hour,
                minute=calendar.close.minute,
                second=0,
                microsecond=0,
            )
        else:
            self.market_open = self.market_close = None
        super().__init__(qm)

    async def _is_personal_order_completed(
        self, order_id: str
    ) -> Tuple[Order.EventType, float, float, float]:
        alpaca_order = self.alpaca_rest_client.get_order(order_id=order_id)
        event = (
            Order.EventType.canceled
            if alpaca_order.status in ["canceled", "expired", "replaced"]
            else Order.EventType.pending
            if alpaca_order.status in ["pending_cancel", "pending_replace"]
            else Order.EventType.fill
            if alpaca_order.status == "filled"
            else Order.EventType.partial_fill
            if alpaca_order.status == "partially_filled"
            else Order.EventType.other
        )
        return (
            event,
            float(alpaca_order.filled_avg_price or 0.0),
            float(alpaca_order.filled_qty or 0.0),
            0.0,
        )

    async def is_fractionable(self, symbol: str) -> bool:
        try:
            asset_details = self.alpaca_rest_client.get_asset(symbol)
        except Exception:
            return False

        return asset_details.fractionable

    async def _is_brokerage_account_order_completed(
        self, order_id: str, external_order_id: Optional[str] = None
    ) -> Tuple[Order.EventType, float, float, float]:
        if not self.alpaca_brokage_api_baseurl:
            raise AssertionError(
                "order_on_behalf can't be called, if brokerage configs incomplete"
            )

        endpoint: str = (
            f"/v1/trading/accounts/{external_order_id}/orders/{order_id}"
        )
        tlog(f"_is_brokerage_account_order_completed:{endpoint}")
        url: str = self.alpaca_brokage_api_baseurl + endpoint

        response = await self._get_request(url)
        tlog(f"_is_brokerage_account_order_completed: response: {response}")
        event = (
            Order.EventType.canceled
            if response["status"] in ["canceled", "expired", "replaced"]
            else Order.EventType.pending
            if response["status"] in ["pending_cancel", "pending_replace"]
            else Order.EventType.fill
            if response["status"] == "filled"
            else Order.EventType.partial_fill
            if response["status"] == "partially_filled"
            else Order.EventType.other
        )
        return (
            event,
            float(response.get("filled_avg_price") or 0.0),
            float(response.get("filled_qty") or 0.0),
            0.0,
        )

    async def is_order_completed(
        self, order_id: str, external_order_id: Optional[str] = None
    ) -> Tuple[Order.EventType, float, float, float]:
        return await self._is_brokerage_account_order_completed(
            order_id, external_order_id
        ) if external_order_id else await self._is_personal_order_completed(order_id)

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        return self.market_open, self.market_close

    def get_trading_days(
        self, start_date: date, end_date: date = date.today()
    ) -> pd.DataFrame:
        calendars = self.alpaca_rest_client.get_calendar(
            start=str(start_date), end=str(end_date)
        )
        _df = pd.DataFrame.from_dict([calendar._raw for calendar in calendars])
        _df["date"] = pd.to_datetime(_df.date)
        return _df.set_index("date")

    def get_position(self, symbol: str) -> float:
        pos = self.alpaca_rest_client.get_position(symbol)

        return float(pos.qty) if pos.side == "long" else -1.0 * float(pos.qty)

    def to_order(self, alpaca_order: AlpacaOrder) -> Order:
        event = (
            Order.EventType.canceled
            if alpaca_order.status in ["canceled", "expired", "replaced"]
            else Order.EventType.pending
            if alpaca_order.status in ["pending_cancel", "pending_replace"]
            else Order.EventType.fill
            if alpaca_order.status == "filled"
            else Order.EventType.partial_fill
            if alpaca_order.status == "partially_filled"
            else Order.EventType.other
        )
        return Order(
            order_id=alpaca_order.id,
            symbol=alpaca_order.symbol.lower(),
            event=event,
            price=float(alpaca_order.limit_price or 0.0),
            side=Order.FillSide[alpaca_order.side],
            filled_qty=float(alpaca_order.filled_qty),
            remaining_amount=float(alpaca_order.qty)
            - float(alpaca_order.filled_qty),
            submitted_at=alpaca_order.submitted_at,
            avg_execution_price=alpaca_order.filled_avg_price,
            trade_fees=0.0,
        )

    def _json_to_order(
        self,
        brokerage_response: dict,
        external_account_id: Optional[str] = None,
    ) -> Order:
        event = (
            Order.EventType.canceled
            if brokerage_response["status"]
            in ["canceled", "expired", "replaced"]
            else Order.EventType.pending
            if brokerage_response["status"]
            in ["pending_cancel", "pending_replace"]
            else Order.EventType.fill
            if brokerage_response["status"] == "filled"
            else Order.EventType.partial_fill
            if brokerage_response["status"] == "partially_filled"
            else Order.EventType.other
        )
        return Order(
            order_id=brokerage_response["id"],
            symbol=brokerage_response["symbol"].lower(),
            event=event,
            price=float(brokerage_response["limit_price"] or 0.0),
            side=Order.FillSide[brokerage_response["side"]],
            filled_qty=float(brokerage_response["filled_qty"]),
            remaining_amount=float(brokerage_response["qty"])
            - float(brokerage_response["filled_qty"]),
            submitted_at=pd.Timestamp(
                ts_input=brokerage_response["submitted_at"],
                unit="ms",
                tz="US/Eastern",
            ),
            avg_execution_price=brokerage_response["filled_avg_price"],
            trade_fees=0.0,
            external_account_id=external_account_id,
        )

    async def get_order(self, order_id: str) -> Order:
        return self.to_order(self.alpaca_rest_client.get_order(order_id))

    def is_market_open_today(self) -> bool:
        return self.market_open is not None

    def get_time_market_close(self) -> Optional[timedelta]:
        if not self.is_market_open_today():
            raise AssertionError("Market closed today")

        return (
            self.market_close - datetime.now(nyc)
            if self.market_close
            else None
        )

    async def reconnect(self):
        self.alpaca_rest_client = REST(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )

    async def run(self) -> asyncio.Task:
        if not self.running_task:
            tlog("starting Alpaca listener")
            self.running_task = asyncio.create_task(
                self.alpaca_ws_client._trading_ws._run_forever()
            )
        return self.running_task

    async def close(self):
        if not self.alpaca_ws_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")
        if self.running_task:
            await self.alpaca_ws_client.stop_ws()

    async def get_tradeable_symbols(self) -> List[str]:
        data = self.alpaca_rest_client.list_assets()
        return [asset.symbol.lower() for asset in data if asset.tradable]

    async def get_shortable_symbols(self) -> List[str]:
        data = self.alpaca_rest_client.list_assets()
        return [
            asset.symbol.lower()
            for asset in data
            if asset.tradable and asset.easy_to_borrow and asset.shortable
        ]

    async def is_shortable(self, symbol) -> bool:
        asset = self.alpaca_rest_client.get_asset(symbol.upper())
        return (
            asset.tradable is not False
            and asset.shortable is not False
            and asset.status != "inactive"
            and asset.easy_to_borrow is not False
        )

    async def _cancel_personal_order(self, order_id: str) -> bool:
        self.alpaca_rest_client.cancel_order(order_id)
        return True

    async def _cancel_brokerage_order(
        self, account_id: str, order_id: str
    ) -> bool:
        if not self.alpaca_brokage_api_baseurl:
            raise AssertionError(
                "_cancel_brokerage_order can't be called, if brokerage configs incomplete"
            )

        endpoint: str = f"/v1/trading/accounts/{account_id}/orders/{order_id}"
        url: str = self.alpaca_brokage_api_baseurl + endpoint

        response_code = await self._delete_request(url)
        tlog(
            f"cancel_brokerage_order {account_id},{order_id} -> {response_code}"
        )
        return response_code == 204

    async def cancel_order(self, order: Order) -> bool:
        if order.external_account_id:
            return await self._cancel_brokerage_order(
                order.external_account_id, order.order_id
            )

        return await self._cancel_personal_order(order.order_id)

    async def _personal_submit(
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
        on_behalf_of: str = None,
    ) -> Order:
        o = self.alpaca_rest_client.submit_order(
            symbol.upper(),
            str(qty),
            side,
            order_type,
            time_in_force,
            limit_price,
            stop_price,
            client_order_id,
            extended_hours,
            order_class,
            take_profit,
            stop_loss,
            trail_price,
            trail_percent,
        )

        return self.to_order(o)

    async def _post_request(self, url: str, payload: Dict) -> Dict:
        response = requests.post(
            url=url,
            json=payload,
            auth=HTTPBasicAuth(
                self.alpaca_brokage_api_key, self.alpaca_brokage_api_secret
            ),
        )

        if response.status_code in (429, 504):
            if "x-ratelimit-reset" in response.headers:
                tlog(
                    f"ALPACA BROKERAGE rate-limit till {response.headers['x-ratelimit-reset']}"
                )
                asyncio.sleep(
                    int(time.time())
                    - int(response.headers["x-ratelimit-reset"])
                )
                tlog("ALPACA BROKERAGE going to retry")
            else:
                tlog(
                    f"ALPACA BROKERAGE push-back w/ {response.status_code} and no x-ratelimit-reset header"
                )
                asyncio.sleep(10.0)

            return await self._post_request(url, payload)

        if response.status_code in (200, 201, 204):
            return response.json()

        raise AssertionError(
            f"HTTP ERROR {response.status_code} from ALPACA BROKERAGE API with error {response.text}"
        )

    async def _get_request(self, url: str) -> Dict:
        response = requests.get(
            url=url,
            auth=HTTPBasicAuth(
                self.alpaca_brokage_api_key, self.alpaca_brokage_api_secret
            ),
        )

        if response.status_code in (429, 504):
            if "x-ratelimit-reset" in response.headers:
                tlog(
                    f"ALPACA BROKERAGE rate-limit till {response.headers['x-ratelimit-reset']}"
                )
                asyncio.sleep(
                    int(time.time())
                    - int(response.headers["x-ratelimit-reset"])
                )
                tlog("ALPACA BROKERAGE going to retry")
            else:
                tlog(
                    f"ALPACA BROKERAGE push-back w/ {response.status_code} and no x-ratelimit-reset header"
                )
                asyncio.sleep(10.0)

            return await self._get_request(url)

        if response.status_code in (200, 201, 204):
            return response.json()

        raise AssertionError(
            f"HTTP ERROR {response.status_code} from ALPACA BROKERAGE API with error {response.text}"
        )

    async def _delete_request(self, url: str) -> int:
        response = requests.delete(
            url=url,
            auth=HTTPBasicAuth(
                self.alpaca_brokage_api_key, self.alpaca_brokage_api_secret
            ),
        )
        # TODO: create a decorator the the re-try / push-backs from server instead of copying.
        if response.status_code in (429, 504):
            if "x-ratelimit-reset" in response.headers:
                tlog(
                    f"ALPACA BROKERAGE rate-limit till {response.headers['x-ratelimit-reset']}"
                )
                asyncio.sleep(
                    int(time.time())
                    - int(response.headers["x-ratelimit-reset"])
                )
                tlog("ALPACA BROKERAGE going to retry")
            else:
                tlog(
                    f"ALPACA BROKERAGE push-back w/ {response.status_code} and no x-ratelimit-reset header"
                )
                asyncio.sleep(10.0)

            return await self._delete_request(url)

        return response.status_code

    async def _order_on_behalf(
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
        on_behalf_of: str = None,
    ) -> Order:
        if not self.alpaca_brokage_api_baseurl:
            raise AssertionError(
                "order_on_behalf can't be called, if brokerage configs incomplete"
            )

        endpoint: str = f"/v1/trading/accounts/{on_behalf_of}/orders"
        url: str = self.alpaca_brokage_api_baseurl + endpoint

        payload = {
            "symbol": symbol.upper(),
            "qty": qty,
            "side": side,
            "type": order_type,
        }

        if limit_price:
            payload["limit_price"] = limit_price
        if time_in_force:
            payload["time_in_force"] = time_in_force

        json_response: Dict = await self._post_request(
            url=url, payload=payload
        )
        tlog(f"ALPACA BROKERAGE RESPONSE: {json_response}")

        return self._json_to_order(json_response, on_behalf_of)

    async def submit_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        order_type: str,
        time_in_force: str = "day",
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
        if on_behalf_of:
            return await self._order_on_behalf(
                symbol,
                qty,
                side,
                order_type,
                time_in_force,
                limit_price,
                stop_price,
                client_order_id,
                extended_hours,
                order_class,
                take_profit,
                stop_loss,
                trail_price,
                trail_percent,
                on_behalf_of,
            )
        else:
            return await self._personal_submit(
                symbol,
                qty,
                side,
                order_type,
                time_in_force,
                limit_price,
                stop_price,
                client_order_id,
                extended_hours,
                order_class,
                take_profit,
                stop_loss,
                trail_price,
                trail_percent,
                on_behalf_of,
            )

    @classmethod
    def _trade_from_dict(cls, trade_dict: Entity) -> Optional[Trade]:
        if trade_dict.event == "new":
            return None

        return Trade(
            order_id=trade_dict.order["id"],
            symbol=trade_dict.order["symbol"].lower(),
            event=Order.EventType.canceled
            if trade_dict.event
            in ["canceled", "suspended", "expired", "cancel_rejected"]
            else Order.EventType.rejected
            if trade_dict.event == "rejected"
            else Order.EventType.fill
            if trade_dict.event == "fill"
            else Order.EventType.partial_fill
            if trade_dict.event == "partial_fill"
            else Order.EventType.other,
            filled_qty=float(trade_dict.qty),
            trade_fee=0.0,
            filled_avg_price=float(
                trade_dict.order["filled_avg_price"] or 0.0
            ),
            liquidity="",
            updated_at=pd.Timestamp(
                ts_input=trade_dict.order["updated_at"],
                unit="ms",
                tz="US/Eastern",
            ),
            side=Order.FillSide[trade_dict.order["side"]],
        )

    @classmethod
    async def trade_update_handler(cls, data):
        try:
            # cls.get_instance().queues[symbol].put(
            #    data.__dict__["_raw"], timeout=1
            # )
            trade = cls._trade_from_dict(data)
            if not trade:
                return

            to_send = {
                "EV": "trade_update",
                "symbol": trade.symbol.lower(),
                "trade": trade.__dict__,
            }
            for q in cls.get_instance().queues.get_allqueues():
                q.put(to_send, timeout=1)

        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {trade.symbol} is FULL:{f}, sleeping for 2 seconds and re-trying."
            )
            raise
        # except AssertionError:
        #    for q in cls.get_instance().queues.get_allqueues():
        #        q.put(data.__dict__["_raw"], timeout=1)
        except Exception as e:
            tlog(f"[EXCEPTION] process_message(): exception {e}")
            if config.debug_enabled:
                traceback.print_exc()
