import asyncio
import queue
import traceback
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd
from alpaca_trade_api.rest import REST, URL
from alpaca_trade_api.stream import Stream
from pytz import timezone

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper
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

    async def is_order_completed(self, order) -> Tuple[bool, float]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        status = self.alpaca_rest_client.get_order(order_id=order.id)
        if status.filled_qty == order.qty:
            return True, float(status.filled_avg_price)

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

    async def get_order(self, order_id: str):
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")
        return self.alpaca_rest_client.get_order(order_id)

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
        return [asset.symbol for asset in data if asset.tradable]

    async def get_shortable_symbols(self) -> List[str]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        data = self.alpaca_rest_client.list_assets()
        return [
            asset.symbol
            for asset in data
            if asset.tradable and asset.easy_to_borrow and asset.shortable
        ]

    async def is_shortable(self, symbol) -> bool:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        asset = self.alpaca_rest_client.get_asset(symbol)
        return (
            asset.tradable is not False
            and asset.shortable is not False
            and asset.status != "inactive"
            and asset.easy_to_borrow is not False
        )

    async def cancel_order(self, order_id: str):
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

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
    ):
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated Alpaca client")

        return self.alpaca_rest_client.submit_order(
            symbol,
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
