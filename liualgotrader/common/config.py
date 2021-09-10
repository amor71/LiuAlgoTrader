import os
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from asyncpg.pool import Pool

from liualgotrader.common.types import BrokerType, DataConnectorType

tradeplan_folder: str = (
    os.getenv("TRADEPLAN_DIR", ".")
    if len(os.getenv("TRADEPLAN_DIR", ".")) > 0
    else "."
)
configuration_filename: str = "tradeplan.toml"
miner_configuration_filename: str = "miner.toml"
env: str


data_connector: DataConnectorType = DataConnectorType[os.getenv("DATA_CONNECTOR", "alpaca")]  # type: ignore

# Performance & Debugging
trace_enabled = bool(int(os.getenv("LIU_TRACE_ENABLED", 0)))
debug_enabled = bool(int(os.getenv("LIU_DEBUG_ENABLED", 0)))

#
# Broker
#
broker: BrokerType = BrokerType.alpaca
#
# Market Schedule
#
bypass_market_schedule: bool
market_open: datetime
market_close: datetime

# total number of tickers to follow
total_tickers = 9000

#
# Shared data
#
build_label: str
filename: str
db_conn_pool: Pool
batch_id: str

#
# API keys
#
# Replace these with your API connection info from the dashboard
polygon_api_key = os.getenv("POLYGON_API_KEY")
alpaca_base_url = os.getenv("APCA_API_BASE_URL")
alpaca_api_key = os.getenv("APCA_API_KEY_ID")
alpaca_api_secret = os.getenv("APCA_API_SECRET_KEY")
alpaca_data_feed = os.getenv("ALPACA_DATA_FEED", "sip")
alpaca_stream_url = os.getenv("ALPACA_STREAM_URL")

finnhub_api_key = os.getenv("FINNHUB_API_KEY")
finnhub_base_url = os.getenv("FINNHUB_BASE_URL")
finnhub_websocket_limit = 50
#
# Execution details (env variable)
dsn: str = os.getenv("DSN", "")


# Stop limit to default to
default_stop = 0.95

# How much of our portfolio to allocate to any one position
risk = 0.001
portfolio_value: Optional[float] = None

group_margin = 0.02

# trade times
market_liquidation_end_time_minutes: int = 15


#
# WS Data Channels
#
WS_DATA_CHANNELS: List[str]


# performance parameters
proc_factor: float = float(os.getenv("CPU_FACTOR", "2.0"))
num_consumers: int = int(os.getenv("NUM_CONSUMERS", "0"))

num_consumer_processes_ratio: int
# polygon parameters
polygon_seconds_timeout = 60


@dataclass
class polygon:
    MAX_DAYS_TO_LOAD: int = 7
