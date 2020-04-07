"""Global data shared during trading"""
from typing import Dict, List, Tuple

from alpaca_trade_api.entity import Order
from asyncpg.pool import Pool

from strategies.base import Strategy

#
# Shared data
#
build_label: str
filename: str
db_conn_pool: Pool

strategies: List[Strategy] = []
open_orders: Dict[str, Tuple[Order, str]] = {}
open_order_strategy: Dict[str, Strategy] = {}
latest_cost_basis: Dict[str, float] = {}
sell_indicators: Dict[str, Dict] = {}
buy_indicators: Dict[str, Dict] = {}
positions: Dict[str, float] = {}
target_prices: Dict[str, float] = {}
stop_prices: Dict[str, float] = {}
partial_fills: Dict[str, float] = {}
