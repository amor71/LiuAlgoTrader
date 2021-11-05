#!/bin/bash
set -e

# values can be either "polygon"/"alpaca"/"gemini"/"finnhub"
export DATA_CONNECTOR="alpaca"

# which broker to use? alpaca/gemini
export LIU_BROKER="alpaca"

# Polygon API key
export POLYGON_API_KEY=""

# Alpaca Credentials, note base URL needs to be changed
# when switching to LIVE account
export APCA_API_BASE_URL="https://paper-api.alpaca.markets"
export ALPACA_STREAM_URL="wss://stream.data.alpaca.markets/v2/sip"
export APCA_API_KEY_ID=""
export APCA_API_SECRET_KEY=""

# "sip" for PRO subscriptions, "iex" for free
export alpaca_data_feed="sip" 

# Gemini 
export GEMINI_API_KEY=
export GEMINI_API_SECRET=

# lock number of CPUs & consumer processes to use
export CPU_FACTOR=4
export NUM_CONSUMERS=4

# Where to look for tradeplan.toml
export TRADEPLAN_DIR=.

# Enable tracing, using OpenTelemetry, enabled = 1, disabled = 0 (DEFAULT)
export LIU_TRACE_ENABLED=0

# Enable debugging,  enabled = 1, disabled = 0 (DEFAULT)
export LIU_DEBUG_ENABLED=1
