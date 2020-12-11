Using Liu
=========

.. # define a hard line break for HTML
.. |br| raw:: html

   <br />

LiuAlgoTrader exposes three applications and a set of
analysis notebooks.

The applications are:

- *trader*
- *backtester*
- *market_miner*



This section describes the three applications,
while the notebooks are described in the `Analysis` section.

No Liability Disclaimer
-----------------------
LiuAlgoTrader is provided with sample scanners and
out-of-the-box strategies. You may choose to use it,
modify it or completely disregard it - Regardless,
LiuAlgoTrader and its Authors bare no responsibility
to any possible loses from using LiuAlgoTrader,
or any of its derivatives (on the other hand, they
also won't share your profits, if there are any).


*trader*
--------

The trader application is the main application in
the LiuAlgoTrading package and it run algorithmic
trading using the Alpaca Markets APIs.

Prerequisites
*************
1. Installed & configured `PostgreSQL` instance, hosting a database w/ LiuAlgoTrader schema,
2. Ensuring environment variables are properly set including Alpaca Market API credentials, and the database DSN,
3. An exiting *tradeplan.toml* at the folder where the trader application is executed. For more details on how to setup the trade plan configuration file, see  `How to Configure` section.

Trading session
***************
Each run of the `trader` application generates a unique
`batch-id`. The `batch-id` is displayed at the beginning
of the execution of the  `trader` application, as well
as at the end of the session.

All trades done during a trade session (and based on the
tradeplan defined in the `tradeplan.toml` file) are
associated to the `batch-id`. This is important when
analysing a trading day, or backtesting. When you backtest,
you re-run a batch-id, simulating market condition while
applying changes to the strategies being used.

**Note**: If a trading session is interrupted, the next run of
the `trader` application will review all current open
positions, and if such exist, and are found in an earlier
session, the trades done at the earlier session will be
`relocated` to the new session - this is done in order to
simplify trade session analysis. See the Analysis section
for more information.

Off-hours
*********
Once the day-trading ends, and all processes (scanners, consumers and producer) are done, off-hour tasks will run.

Currently supported tasks include:

* `gain_loss` : Populating gain_loss DB table is aggregated results per symbol, per algo_run_id.



Usage
*****

To run the market_miner app type:

.. code-block:: bash

    trader

An expected beginning of execution should look like:

.. image:: /images/trader-usage1.png
    :width: 600
    :align: left
    :alt: *trader* output

**Notes**

- Normally the *trader* application should be run before the start of the trading day, or during the trading day.
- When trying to run the *trader* on a none trading day, or after the trading day ended, the *trader* application will present an error message indicating the next open of the trading day.
- It is possible to by-pass the trading-day limitations (very useful when debugging custom scanners or trade strategies), by adding to the *tradeplan.toml* file:

.. code-block:: bash

    bypass_market_schedule = true

Understanding *trader* output and Logging
*****************************************

The *trader* application writes output to STDOUT
(standard output), however, it will also send
logging to `google-cloud-logging` if those are
configured. To learn more on how to configure
this feature read
the `How to Install & Setup` section.

The *trader* application uses a producer-consumers
design patterns. In other words, when executed the
scanners would run according to the tradeplan
specifications, and then a single producer process
will spawn and a collection of consumer processes.
To understand the inner workings
read the `Understanding what's under the hood` section.

The *trader* application writes log outs in sections
to help troubleshooting and for better readability.

- The first section presents the filename being executed (`trader` in most cases) followed by a unique-id (GUID) which represents the trading session. Each time the `trader` application is run, a new batch-id will be created. To understand more read the `How to analyze your trades` section.
- The second section displays non-secure environment variables that may affect the trading beviour. You should see the DSN (database connection string) properly displayed, and when you don't that's normally a sign that the env variables were not properly set.
- The third section displays the location of the trade-plan file, and parsing of the trade-plan header. A basic validation of the trade-plan file is done during that point and error messages will be presented for crudely format erros.
- The fourth section normally displays the scanner execution. For more details on scanners read the `Scanners` section.
- The fifth and last section displays the strategies execution. For more details on strategies read the `Strategies` section.


Liquidation
***********

15 minutes before end of the trading-day
LiuAlgoTrader will start closing positions,
you need to be aware of this behaviour if you
build custom strategies for end-of-day.


*backtester*
------------

The main purpose of Liu Algo Trading Framework is running
an optimized, high-performance trading sessions either in
paper or live trading sessios. However, the framework also comes
equipped with a basic `back-test` -ing tool. The tool allow re-running
past trading sessions on revised strategies.

The tool comes in two 'favours': command-line tool and a browser-based UI using `streamlit`. The functionality of both tools is not exactly the same, please read the details below.

**NOTE:** While the `trader` application acts on events per-second, the `backtester` application runs on per-minute data.

Prerequisites
*************
1. Installed and configured Liu Algo Tradring Framework.
2. An exiting *tradeplan.toml* at the folder where the trader application is executed. For more details on how to setup the trade plan configuration file, see  `How to Configure` section,
3. [Optional] The batch-id (UUID) of a trade session to replay.

Command-line tool
*****************

To run the `backtester` application type:

.. code-block:: bash

    backtester

Displays a high-level description of the tool, and it's different parameters:

.. image:: /images/backtester1.png
    :width: 800
    :align: left
    :alt: *backtester* usage


If you had run a `trader` session  (or have used `liu quickstart` wizard) the
database should should hold at least one batch-id.

To get a list of previous trading sessions, run:

.. code-block:: bash

    backtester --batch-list

An example output:

.. image:: /images/backtester2.png
    :width: 800
    :align: left
    :alt: *backtester* batch-list

|br|

When running a back-test session, it's possible to
re-run strategies on all symbols selected by the scanners
for that trading session, or limit the back-test session
only to stocks actually traded by strategies on that
specific batch-id. To limit the back-test session to
actually traded symbols use the `--strict` command-line option.


Below is a sample output of a running `backtester` application:

.. image:: /images/backtester3.png
    :width: 800
    :align: left
    :alt: *backtester* sample run

|br|
|br|
**Notes**:

1. A backtest session creates a new `batch-id`. This is helpful when running analysis of a backtest session. See the Analysis section for more details.
2. Strategies running in a backtesting session are marked with `BACKTEST` environment when logging trades, this is helpful to distinguish between backtest trades, paper and live trades when querying the database.
3. When the `backtester` application starts, it lists all the stocks picked by the scanners during the trading session.
4. `backtester` re-runs each session, by loading per-minute candles for the stock trading session (up to one week back). This reply simulates per-minute trading, vs. per-second trading during `trader` execution (though, the `trader` application can also be configured to execute strategies per minute and not per secord).
5.  `backtester` supports a debug mode, per symbol. The debug flag is passed to the implementation for `Strategy.run()`, allowing more verbose logging during backtesting.

Understanding command-line parameters
*************************************


+----------------+-------------------------------------------------------+
| Parameter Name | Description                                           |
+----------------+-------------------------------------------------------+
| symbol         | Normally, the `backtester` application loads          |
|                | symbols from a previously executed batch, the symbol  |
|                | parameter changes this behavior by selecting a        |
|                | specific symbol to back-test during the batch         |
|                | timeframe (even if the stock was not picked by        |
|                | a scanner during `trader` session). It is possible    |
|                | to include several --symbol parameters in a single    |
|                | `backtester` application execution.                   |
+----------------+-------------------------------------------------------+
| strict         | This option, limits the back-tested symbol to         |
|                | symbol that were actually traded during a session.    |
|                | The option is helpful to speed up back-test run       |
|                | during initial strategy development or improvement    |
|                | session.                                              |
+----------------+-------------------------------------------------------+
| duration       | The option over-rides the initial duration specified  |
|                | in the back-tested `tradeplan`. The option is less    |
|                | relevant for tradeplans with multiple trade windows.  |
+----------------+-------------------------------------------------------+
| debug          | When a sybmol is select for debug, then the debug     |
|                | flag will be passed as True for the strategy          |
|                | `run()` function. Based on the strategy implementation|
|                | additional logging may be provided.                   |
+----------------+-------------------------------------------------------+


Browser-base tool
*****************

If you used `liu quickstart` wizard, or watched the intro video_ you've already seen
the browser based tool in action.

.. _video: https://youtu.be/rVwFCbHsbIY

To run the tool type:

.. code-block:: bash

    streamlit run https://raw.github.com/amor71/LiuAlgoTrader/master/analysis/backtester_ui.py

Once the browser opens, it would look like:

.. image:: /images/streamlit-backtest-1.png
    :width: 800
    :align: left
    :alt: *backtester* streamlit start sample

The browser-based UI supports two types on back-testing sessions:

1. Re-running strategies for a specific trading session. Similarly to the command-line tool,
2. Re-run strategies on a past date, **even if no past trading session took place on that date**. This capability is not yet exposed on the command-line tool.

**IMPORTANT NOTES**

1. When selecting the "`back-test against the whole day`" option , **scanners** will be called w/ a `back-time` schedule (vs. real-time),
2. Scanners are expected to support running in `back_time` mode (see scanners section).
3. The built-in scanner supports back-time mode - if no data exists in the database for that specific date, the framework would load OHLC data for all traded stock on the select date, and the day before. Please note that this process may take between long minutes to couple of hours (on-time) depending on your network connection & equipment.
4. Instead of having the scanners trigger loading of data, it is advised to use the `market_miner` tool to pre-load data in off-hours before running a back-test session on a day without any data.

*market_miner*
--------------

While the `trader` application is used for
real-time calculations, the `market_miner`
application is intended for off-market, batch
calculations and data collections.

The `market_miner` application is configured by
the `miner.toml` configuration file. Quite similarly
to how the trader application is configured by the
`tradeplan.toml` TOML configuration file.

An example `miner.toml` file:

.. literalinclude:: ../../miner.toml
  :language: python
  :linenos:

miners
******

Currently two miner are supported:


- `StockCluster` : the miner read all trade-able stocks, and stores in the `ticker_data` table the industry/segment and similar stocks details. This data can later be used in real-time to compare how a certain stock is doing against an industry/segment or similar stocks index.
- `DailyOHLC` : the miner collect Daily OHLC data for trade-able stocks, and stores the details in the `stock_ohlc` table. The miner gets number of days configuration parameters while ensure that at least that number of data data exists. Additionally, the miner can calculate specific indicators which can be used later during real-time calculations.


**Note**

the `market_miner` app should be executed in
off-hours, and once run it will refresh existing data, or load data since last run.

Prerequisites
*************

1. Installed & configured `PostgreSQL` instance, hosting a database w/ LiuAlgoTrader schema,
2. Ensuring environment variables are properly set including Alpaca Market API credentials, and the database DSN,

Usage
*****

To run the market_miner app type:

.. code-block:: bash

    market_miner

The expected result should look like:

.. image:: /images/market-miner-usage.png
    :width: 600
    :align: left
    :alt: *market_miner* output




