What's New
----------

+------------------+----------------------------------------------+
| Release          | Notes                                        |
+------------------+----------------------------------------------+
| 0.0.76           | adding `anchored-vwap` calculation, and      |
|                  | notebook w/ advanced visuals.                |
+------------------+----------------------------------------------+
| 0.0.74           | 1. adding `symbol` and `duration` parameters |
|                  |    to `backtester`, updated documentation,   |
|                  | 2. clean-ups to back-testing notebook.       |
+------------------+----------------------------------------------+
| 0.0.72           | 1. Windows deployment fixes,                 |
|                  | 2. Fixes & improvements to analysis tools    |
+------------------+----------------------------------------------+
| 0.0.69           | added analytical notebooks incl.             |
|                  | tear_sheet, deep_analysis                    |
+------------------+----------------------------------------------+
| 0.0.67           | Adding setup wizard (`liu quickstart`)       |
|                  | as well as reducing dependencies on          |
|                  | external libraries to simplify install       |
|                  | process for Windows users.                   |
|                  +----------------------------------------------+
|                  | Introduction of `streamlit`  visual          |
|                  | tool for running back-test sessions and      |
|                  | analysis.                                    |
|                  +----------------------------------------------+
|                  | Analysis notebooks' cleanup                  |
|                  +----------------------------------------------+
|                  | Adding configuration parameters              |
|                  | to `tradeplan.toml` file (see Examples):     |
|                  | portfolio_value = 100000.00                  |
|                  | risk = 0.001                                 |
|                  | market_liquidation_end_time_minutes = 15     |
|                  +----------------------------------------------+
|                  | Improved documentation                       |
+------------------+----------------------------------------------+
| 0.0.55           | Fixes to build process                       |
|                  +----------------------------------------------+
|                  | Adding two configuration parameters          |
|                  | to `tradeplan.toml` file (see example)       |
|                  | to help debugging:                           |
|                  | **skip_existing = true** to skip             |
|                  | loading open positions                       |
|                  | **test_scanners = true** to debug            |
|                  | scanners only (no other process              |
|                  | would run)                                   |
|                  +----------------------------------------------+
|                  | TRADEPLAN_DIR added env variable to          |
|                  | control `tradeplan` location.                |
+------------------+----------------------------------------------+
| 0.0.50           | 1. Scanner may direct picks to a             |
|                  | specific strategy, allowing  several         |
|                  | scanners, and several strategies to          |
|                  | run in parallel.                             |
|                  +----------------------------------------------+
|                  | 2. market_miner application expanded         |
|                  | to allow custome off-hour calculations       |
|                  | including collection of daily OHLC data      |
|                  | and calculating custom indicators.           |
+------------------+----------------------------------------------+

