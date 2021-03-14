#!/bin/bash
set -e

# Database connection string
export DSN="postgresql://momentum@localhost/tradedb"

# Which data providers to use values maybe polygon/alpaca (finnhub coming soon)
export DATA_CONNECTOR="polygon"

# Polygon API key
export POLYGON_API_KEY=""

# Alpaca Credentials, note base URL needs to be changed
# when switching to LIVE account
export ALPACA_BASEURL="https://paper-api.alpaca.markets"
export APCA_API_KEY_ID=""
export APCA_API_SECRET_KEY=""

# "sip" for PRO subscriptions
export alpaca_data_feed="iex" 

# max number of symbols to trade in parallel
export LIU_MAX_SYMBOLS=440

# lock number of CPUs & consumer processes to use
export CPU_FACTOR=4
export NUM_CONSUMERS=4

# Where to look for tradeplan.toml
export TRADEPLAN_DIR=.
