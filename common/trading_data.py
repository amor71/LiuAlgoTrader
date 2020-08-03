"""Global data shared during trading"""
from asyncio import Queue
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from alpaca_trade_api.entity import Order

from models.ticker_snapshot import TickerSnapshot
from strategies.base import Strategy

strategies: List[Strategy] = []
open_orders: Dict[str, Tuple[Order, str]] = {}
open_order_strategy: Dict[str, Strategy] = {}
last_used_strategy: Dict[str, Strategy] = {}
latest_cost_basis: Dict[str, float] = {}
sell_indicators: Dict[str, Dict] = {}
buy_indicators: Dict[str, Dict] = {}
positions: Dict[str, float] = {}
target_prices: Dict[str, float] = {}
stop_prices: Dict[str, float] = {}
partial_fills: Dict[str, float] = {}
symbol_resistance: Dict[str, float] = {}

industry_trend: Dict[str, float] = {}
sector_trend: Dict[str, float] = {}
snapshot: Dict[str, TickerSnapshot] = {}

cool_down: Dict[str, Optional[datetime]] = {}

queues: Dict[str, Queue] = {}
down_cross: Dict[str, datetime] = {}
