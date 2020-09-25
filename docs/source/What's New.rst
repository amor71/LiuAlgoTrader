What's New
----------


+------------------+-----------------------------------------+
| Release          | Notes                                   |
+------------------+-----------------------------------------+
| 0.0.55           | Fixes to build process                  |
|                  +-----------------------------------------+
|                  | Adding two configuration parameters     |
|                  | to `tradeplan.toml` file (see example)  |
|                  | to help debugging:                      |
|                  | **skip_existing = true** to skip        |
|                  | loading open positions                  |
|                  | **test_scanners = true** to debug       |
|                  | scanners only (no other process         |
|                  | would run)                              |
+------------------+-----------------------------------------+
| 0.0.50           | 1. Scanner may direct picks to a        |
|                  | specific strategy, allowing  several    |
|                  | scanners, and several strategies to     |
|                  | run in parallel.                        |
|                  +-----------------------------------------+
|                  | 2. market_miner application expanded    |
|                  | to allow custome off-hour calculations  |
|                  | including collection of daily OHLC data |
|                  | and calculating custom indicators.      |
+------------------+-----------------------------------------+

