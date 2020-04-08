import os
from datetime import datetime

#
# API keys
#
# Replace these with your API connection info from the dashboard
paper_base_url = "https://paper-api.alpaca.markets"
paper_api_key_id = "PKO3OSD9LU9GTQPL69GO"
paper_api_secret = "chnPFlGXbY4Y4QAAZ3Q7MJHxkxBYB30CQZNVZTaj"

#
# Execution details (env variable)
#
env: str = os.getenv("TRADE", "PAPER")
dsn: str = os.getenv("DSN", "")
trade_buy_window: int = int(os.getenv("TRADE_BUY_WINDOW", "120"))

prod_base_url = "https://api.alpaca.markets"
prod_api_key_id = "AKVKN4TLUUS5MZO5KYLM"
prod_api_secret = "nkK2UmvE1kTFFw1ZlaqDmwCyiuCu7OOeB5y2La/X"


#
# Trading parameters
#
# We only consider stocks with per-share prices inside this range
min_share_price = 2.0
max_share_price = 20.0

# Minimum previous-day dollar volume for a stock we might consider
min_last_dv = 500000

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

#
# Bypasses
#
bypass_market_schedule: bool = False
