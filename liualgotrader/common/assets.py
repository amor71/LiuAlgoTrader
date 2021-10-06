from typing import Dict

from liualgotrader.common.types import AssetType

assets_details: Dict[str, Dict] = {
    "BTCUSD": {
        "type": AssetType.CRYPTO,
        "min_order_size": 0.00001,
        "tick_precision": 8,
    },
    "ETHUSD": {
        "type": AssetType.CRYPTO,
        "min_order_size": 0.001,
        "tick_precision": 6,
    },
}


def get_asset_precision(asset_name: str) -> int:
    if asset_name not in assets_details:
        raise ValueError(f"asset name {asset_name} is undefined")

    return assets_details[asset_name]["tick_precision"]


def round_asset(asset_name: str, value: float) -> float:
    return round(value, get_asset_precision(asset_name))


def get_asset_min_qty(asset_name: str) -> float:
    if asset_name not in assets_details:
        raise ValueError(f"asset name {asset_name} is undefined")

    return assets_details[asset_name]["min_order_size"]
