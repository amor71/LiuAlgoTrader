import os
from datetime import datetime
from typing import List

from asyncpg.pool import Pool

#
# Shared data
#
build_label: str
filename: str
db_conn_pool: Pool

#
# API keys
#
# Replace these with your API connection info from the dashboard
paper_base_url = os.getenv("ALPACA_PAPER_BASEURL")
paper_api_key_id = os.getenv("ALPACA_PAPER_API_KEY")
paper_api_secret = os.getenv("ALPACA_PAPER_API_SECRET")
finnhub_api_key = os.getenv("FINNHUB_API_KEY")
finnhub_base_url = os.getenv("FINNHUB_BASE_URL")
finnhub_websocket_limit = 50
#
# Execution details (env variable)
#
env: str = os.getenv("TRADE", "PAPER")
dsn: str = os.getenv("DSN", "")
trade_buy_window: int = int(os.getenv("TRADE_BUY_WINDOW", "120"))

prod_base_url = os.getenv("ALPACA_LIVE_BASEURL")
prod_api_key_id = os.getenv("ALPACA_LIVE_API_KEY")
prod_api_secret = os.getenv("ALPACA_LIVE_API_SECRET")


#
# Trading parameters
#
# We only consider stocks with per-share prices inside this range
min_share_price = 2.0
max_share_price = 20.0

# Minimum previous-day dollar volume for a stock we might consider
min_last_dv = 500000

min_volume_at_open = 30000

# Stop limit to default to
default_stop = 0.95

# How much of our portfolio to allocate to any one position
risk = 0.001

today_change_percent = 3.5

group_margin = 0.02

# trade times
market_cool_down_minutes: int = 15
market_liquidation_end_time_minutes: int = 15
market_open: datetime
market_close: datetime

# total number of tickers to follow
total_tickers = 440

# algo attributes
check_patterns: bool = False
#
# WS Data Channels
#
WS_DATA_CHANNELS: List[str] = ["A", "AM", "T", "Q"]

#
# Bypasses
#
bypass_market_schedule: bool = False

# performance parameters
num_consumer_processes_ratio: int = 75

# polygon parameters
polygon_seconds_timeout = 60
