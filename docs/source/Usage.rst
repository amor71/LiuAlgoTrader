How To Use
==========

LiuAlgoTrader exposes three applications and a set of
analysis notebooks.

The applications are:

- *trader*
- *market_minder*
- *backtester*


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


*market_miner*
--------------

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



backtester
----------



