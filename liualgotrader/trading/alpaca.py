import asyncio
import queue
import traceback
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
from alpaca_trade_api.entity import Order as AlpacaOrder
from alpaca_trade_api.rest import REST, URL, Entity
from alpaca_trade_api.stream import Stream
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import Order, QueueMapper, Trade
from liualgotrader.trading.base import Trader

nyc = timezone("America/New_York")


class AlpacaTrader(Trader):
    def __init__(self, qm: QueueMapper = None):
        self.market_open: Optional[datetime]
        self.market_close: Optional[datetime]

        self.alpaca_rest_client = REST(
            base_url=URL(config.alpaca_base_url),
            key_id=config.alpaca_api_key,
            secret_key=config.alpaca_api_secret,
        )
        if not self.alpaca_rest_client:
            raise AssertionError(
                "Failed to authenticate Alpaca RESTful client"
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

    async def is_order_completed(self, order: Order) -> Tuple[bool, float]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        status = self.alpaca_rest_client.get_order(order_id=order.order_id)
        if status.filled_qty == status.qty:
            return True, float(status.filled_avg_price or 0.0)

        return False, 0.0

    def get_market_schedule(
        self,
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        return self.market_open, self.market_close

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

    async def get_order(self, order_id: str) -> Order:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

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
        if not self.alpaca_rest_client:
            raise AssertionError(
                "Failed to authenticate Alpaca RESTful client"
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
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        data = self.alpaca_rest_client.list_assets()
        return [asset.symbol.lower() for asset in data if asset.tradable]

    async def get_shortable_symbols(self) -> List[str]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        data = self.alpaca_rest_client.list_assets()
        return [
            asset.symbol.lower()
            for asset in data
            if asset.tradable and asset.easy_to_borrow and asset.shortable
        ]

    async def is_shortable(self, symbol) -> bool:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        asset = self.alpaca_rest_client.get_asset(symbol.upper())
        return (
            asset.tradable is not False
            and asset.shortable is not False
            and asset.status != "inactive"
            and asset.easy_to_borrow is not False
        )

    async def cancel_order(
        self, order_id: Optional[str] = None, order: Optional[Order] = None
    ):
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        if order:
            order_id = order.order_id
        self.alpaca_rest_client.cancel_order(order_id)

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
    ) -> Order:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

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

    @classmethod
    def _trade_from_dict(cls, trade_dict: Entity) -> Optional[Trade]:
        if trade_dict.event == "new":
            return None

        print(trade_dict)
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
            filled_qty=float(trade_dict.order["filled_qty"]),
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
