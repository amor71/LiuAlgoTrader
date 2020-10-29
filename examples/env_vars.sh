#!/bin/bash
set -e

# Database connection string
export DSN="postgresql://momentum@localhost/tradedb"

# used for paper-trading accounts
export ALPACA_PAPER_BASEURL="https://paper-api.alpaca.markets"
export ALPACA_PAPER_API_KEY=
export ALPACA_PAPER_API_SECRET=

# used for live-trading accounts
export ALPACA_LIVE_BASEURL="https://api.alpaca.markets"
export APCA_API_KEY_ID=
export APCA_API_SECRET_KEY=

# max number of symbols to trade in parallel
export LIU_MAX_SYMBOLS=440

# lock number of CPUs & consumer processes to use
export CPU_FACTOR=4
export NUM_CONSUMERS=4

# Where to look for tradeplan.toml
export TRADEPLAN_DIR=.
