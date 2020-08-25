import os
from datetime import datetime
from typing import List

from asyncpg.pool import Pool

configuration_filename: str = "tradeplan.toml"

#
# Market Schedule
#
bypass_market_schedule: bool
market_open: datetime
market_close: datetime

# total number of tickers to follow
total_tickers = int(os.getenv("LIU_MAX_SYMBOLS", "100"))

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

prod_base_url = os.getenv("ALPACA_LIVE_BASEURL")
prod_api_key_id = os.getenv("ALPACA_LIVE_API_KEY")
prod_api_secret = os.getenv("ALPACA_LIVE_API_SECRET")


# Stop limit to default to
default_stop = 0.95

# How much of our portfolio to allocate to any one position
risk = 0.001


group_margin = 0.02

# trade times
market_liquidation_end_time_minutes: int = 15


#
# WS Data Channels
#
WS_DATA_CHANNELS: List[str] = ["A", "AM", "T", "Q"]

# performance parameters
num_consumer_processes_ratio: int = 75

# polygon parameters
polygon_seconds_timeout = 60
