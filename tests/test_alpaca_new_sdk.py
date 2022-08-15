from alpaca.data.historical import (CryptoHistoricalDataClient,
                                    StockHistoricalDataClient)
from alpaca.data.requests import StockSnapshotRequest
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.trading.requests import GetAssetsRequest

from liualgotrader.common import config


def test_assets():
    stock_trader = TradingClient(
        config.alpaca_api_key, config.alpaca_api_secret
    )

    print("loaded all assets")
    assets = stock_trader.get_all_assets(
        GetAssetsRequest(
            status=AssetStatus.ACTIVE, asset_class=AssetClass.US_EQUITY
        )
    )

    print("look for BTDPY")
    for asset in assets:
        if asset.tradable and asset.symbol == "BTDPY":
            print(asset)

    print("done")
    return True


def test_snapshot():
    stock_client = StockHistoricalDataClient(
        config.alpaca_api_key, config.alpaca_api_secret
    )

    snapshot = stock_client.get_stock_snapshot(
        StockSnapshotRequest(symbol_or_symbols="BTDPY")
    )

    print(snapshot)

    return True
