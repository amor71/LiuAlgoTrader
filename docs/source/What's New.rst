What's New
----------
+------------------+----------------------------------------------+
| Release          | Notes                                        |
+------------------+----------------------------------------------+
| 0.4.20           | **Major Release**                            |
|                  |                                              |
|                  | 1. Add support for Tradier.                  |
|                  | 2. Refactor momentum.                        |
|                  | 3. Added tests coverage.                     |
|                  | 4. Bug fixes.                                |
+------------------+----------------------------------------------+
| 0.4.13           | 1. Momentum scanner supports both Alpaca and |
|                  |    polygon.                                  |
|                  | 2. `data_loader` takes into account symbol   |
|                  |    name changes.                             |
|                  | 3. Adding data for sp500 symbol changes      |
|                  |    between 2019-2022.                        |
|                  | 4. Bug fixes.                                |
+------------------+----------------------------------------------+
| 0.4.12           | 1. improvements to Crypto data loading.      |
|                  | 2. Adding `list` to portfolio CLI.           |
|                  | 3. Bug fixes.                                |
|                  | 4. Adding Tutorials links.                   |
+------------------+----------------------------------------------+
| 0.4.10           | **Major Release**                            |
|                  |                                              |
|                  | 1. trader application runs until stopped,    |
|                  |    won't start/stop on US Equity markets.    |
|                  | 2. Add support to database-based tradeplan   |
|                  |    (undocumented yet).                       |
|                  | 3. Significant performance improvements.     |
|                  | 4. Complete re-write to DataLoader. Add      |
|                  |    pre-fetching list of symbols concurrently.|
|                  |    Allow concurrent loading of data with     |
|                  |    significant loading time improvements.    |
|                  | 5. Infrastructure for supporting multiple    |
|                  |    users / accounts (undocumented yet).      |
|                  | 6. Added DB Schema browsing web-site.        |
|                  | 7. Massive refactoring and code styling.     |
+------------------+----------------------------------------------+
| 0.4.00           | **Major Release**                            |
|                  |                                              |
|                  | 1. Extend platform to support Crypto assets  |
|                  | 2. Support Gemini Crypto Exchange            |
|                  | 3. Extend to support fractional quantities   |
|                  | 4. Bug-fixes & code improvements             |
+------------------+----------------------------------------------+
| 0.3.26           | bug-fix in strategy creation                 |
+------------------+----------------------------------------------+
| 0.3.25           | 1. Introduce Tracing & Performance           |
|                  |    Monitoring,                               |
|                  | 2. Improving SP500 historical data,          |
|                  | 3. Improve logging and introducing           |
|                  |    trace-back logging,                       |
|                  | 4. Code quality improvements & refactoring   |
+------------------+----------------------------------------------+
| 0.3.22           | Revised documentation                        |
+------------------+----------------------------------------------+
| 0.3.21           | 1. Significant performance improvements,     |
|                  | 2. Bug fixes,                                |
+------------------+----------------------------------------------+
| 0.3.19           | 1. New CLI for portfolio management,         |
|                  | 2. New notebook for portfolio trades,        |
|                  | 3. Revised documentation,                    |
|                  | 4. minor fixes.                              |
+------------------+----------------------------------------------+
| 0.3.18           | fixes for portfolio analysis                 |
+------------------+----------------------------------------------+
| 0.3.16           | Added Windows installation FAQ, code         |
|                  | cleanup, minor improvements & fixes.         |
+------------------+----------------------------------------------+
| 0.3.10           | **Major Release**                            |
|                  |                                              |
|                  | 1. Release `optimizer` application for       |
|                  |    hyper-parameters optimization,            |
|                  | 2. Notebook for optimization session         |
|                  |    review and selection of parameters,       |
|                  | 3. Deployment & Installation fixes,          |
|                  |    transition to travis-ci.com, cleanup      |
|                  |    to pytests,                               |
|                  | 4. Bug-fixes and code improvements.          |
+------------------+----------------------------------------------+
| 0.2.00           | **Major Release**                            |
|                  |                                              |
|                  | 1. Add support for Account managment,        |
|                  | 2. Add support for Portfolio managment,      |
|                  | 3. Add support for key-value store,          |
|                  | 4. Extend Strategy to better support         |
|                  |    'swing' trades, but allow to run          |
|                  |    on all symbols at one go, instead         |
|                  |    of getting real-time updates and actions  |
|                  |    per symbol,                               |
|                  | 5. Improve analytics for swing trading,      |
|                  |    including Sharpe Ratio and SP-500         |
|                  |    comparison,                               |
|                  | 6. Added test-automation,                    |
|                  | 7. Improve documentation.                    |
+------------------+----------------------------------------------+
| 0.1.05           | Alapaca data-provider production ready       |
+------------------+----------------------------------------------+
| 0.1.00           | **Competible Breaking Release**              |
|                  |                                              |
|                  | 1. Added support for Alpaca and Polygon      |
|                  |    `separation`,                             |
|                  | 2. Re-architecting integration w/            |
|                  |    data providers (Polygon) and brokers      |
|                  |    (Alpaca) laying ground for future         |
|                  |    changes,                                  |
|                  | 3. Adding concept of `DataLoader`, little    |
|                  |    bit like how ZipLine works,               |
|                  | 4. Introduce backtesting for long periods    |
|                  |    similarly to ZipLine, creating a full     |
|                  |    backtesting environment,                  |
|                  | 5. Breaking changes to base classes,         |
|                  |    which may result in minor adjustments     |
|                  |    for customer scanners and strategies,     |
|                  | 6. Improved test automation,                 |
|                  | 7. Improved performance.                     |
+------------------+----------------------------------------------+
| 0.0.85           | 1. Added `portfolio` DB table, and           |
|                  |    model support,                            |
|                  | 2. Enhance `market_miner`, to support        |
|                  |    external miners (like scanners, and       |
|                  |    strategies),                              |
|                  | 3. Move `daily_ohlc` miner to examples and   |
|                  |    add documentation,                        |
|                  | 4. Add example miner for momentum strategy,  |
|                  | 5. Add notebook & market_data function for   |
|                  |    for SP500 data-collection, and trend,     |
|                  | 6. Add notebook for SP500 portfolio analysis,|
|                  | 7. Add notebook and function for calculating |
|                  |    strategy p-value,                         |
|                  | 8. Added documentation for changes.          |
|                  | 9. Strategy may `reject` stock, so that it   |
|                  |    will not be presented with that stock     |
|                  |    again during the trading session.         |
+------------------+----------------------------------------------+
| 0.0.80           | 1. Added `gain_loss` and `trade_analysis`    |
|                  |    DB tables,                                |
|                  | 2. Added off-hour task, at the end of the    |
|                  |    trading day which populates `gain_loss`   |
|                  |    and `trade_analysis with P&L data per     |
|                  |    strategy, per symbol or per trade,        |
|                  |    including `r_units` calculations,         |
|                  | 3. Added `Gainloss` market_miner, and        |
|                  |    ease future extension w/ additional miners|
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

