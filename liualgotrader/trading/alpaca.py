from typing import List

from alpaca_trade_api.rest import REST

from liualgotrader.common import config
from liualgotrader.trading.base import Trader


class AlpacaTrader(Trader):
    def __init__(self):
        self.alpaca_rest_client = REST(
            key_id=config.alpaca_api_key, secret_key=config.alpaca_api_secret
        )
        if not self.alpaca_rest_client:
            raise AssertionError(
                "Failed to authenticate Alpaca RESTful client"
            )

        super().__init__()

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
