"""Global data shared during trading"""
from asyncio import Queue
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from alpaca_trade_api.entity import Order

from liualgotrader.models.ticker_snapshot import TickerSnapshot
from liualgotrader.strategies.base import Strategy

strategies: List[Strategy] = []
open_orders: Dict[str, Tuple[Order, str]] = {}
open_order_strategy: Dict[str, Strategy] = {}
last_used_strategy: Dict[str, Strategy] = {}
latest_cost_basis: Dict[str, float] = {}
latest_scalp_basis: Dict[str, float] = {}
sell_indicators: Dict[str, Dict] = {}
buy_indicators: Dict[str, Dict] = {}
positions: Dict[str, float] = {}
target_prices: Dict[str, float] = {}
stop_prices: Dict[str, float] = {}
partial_fills: Dict[str, float] = {}
symbol_resistance: Dict[str, float] = {}
voi: Dict[str, List[float]] = {}
voi_ask: Dict[str, Tuple[float, float, datetime]] = {}
voi_bid: Dict[str, Tuple[float, float, datetime]] = {}


industry_trend: Dict[str, float] = {}
sector_trend: Dict[str, float] = {}
snapshot: Dict[str, TickerSnapshot] = {}

cool_down: Dict[str, Optional[datetime]] = {}

queues: Dict[str, Queue] = {}
down_cross: Dict[str, datetime] = {}

buy_time: Dict[str, datetime] = {}
