import asyncio
import json
import queue
import traceback
from typing import List, Optional

from alpaca_trade_api.rest import REST, URL
from alpaca_trade_api.stream import Stream

from liualgotrader.common import config
from liualgotrader.common.tlog import tlog
from liualgotrader.common.types import QueueMapper
from liualgotrader.trading.base import Trader


class AlpacaTrader(Trader):
    def __init__(self, qm: QueueMapper = None):
        self.alpaca_rest_client = REST(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
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
        self.running = False

        super().__init__(qm)

    async def run(self) -> Optional[asyncio.Task]:
        if not self.running:
            tlog("starting Alpaca listener")
            self.running = True
            return asyncio.create_task(
                self.alpaca_ws_client._trading_ws._run_forever()
            )
        return None

    async def get_tradeable_symbols(self) -> List[str]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")

        data = self.alpaca_rest_client.list_assets()
        return [asset.symbol for asset in data if asset.tradable]

    async def get_shortable_symbols(self) -> List[str]:
        if not self.alpaca_rest_client:
            raise AssertionError("Must call w/ authenticated polygon client")

        data = self.alpaca_rest_client.list_assets()
        return [
            asset.symbol
            for asset in data
            if asset.tradable and asset.easy_to_borrow and asset.shortable
        ]

    @classmethod
    async def trade_update_handler(cls, data):
        symbol = data.__dict__["_raw"]["order"]["symbol"]
        data.__dict__["_raw"]["EV"] = "trade_update"
        data.__dict__["_raw"]["symbol"] = symbol
        try:
            cls.get_instance().queues[symbol].put(
                data.__dict__["_raw"], timeout=1
            )
        except queue.Full as f:
            tlog(
                f"[EXCEPTION] process_message(): queue for {symbol} is FULL:{f}, sleeping for 2 seconds and re-trying."
            )
            raise
        except Exception as e:
            tlog(f"[EXCEPTION] process_message(): exception {e}")
            traceback.print_exc()
