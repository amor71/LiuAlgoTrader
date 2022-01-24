**Trading with Liu**
====================

.. # define a hard line break for HTML
.. |br| raw:: html

   <br />

LiuAlgoTrader has three applications and a set of
analysis notebooks.

The applications are:

- *trader*
- *backtester*
- *market_miner*


This section describes the trader application,


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
the LiuAlgoTrading package and it runs algorithmic
trading using the Alpaca Markets APIs.

Prerequisites
*************
1. Installed & configured `PostgreSQL` instance, hosting a database with LiuAlgoTrader schema,
2. Ensuring environment variables are properly set including Alpaca Market API credentials, and the database DSN,
3. An existing *tradeplan.toml* at the folder where the trader application is executed. For more details on how to setup the trade plan configuration file, see  `How to Configure` section.

Trading session
***************
Each run of the `trader` application generates a unique
`batch-id`. The `batch-id` is displayed at the beginning
of the execution of the  `trader` application, as well
as at the end of the session.

All trades done during a trade session (and based on the
`tradeplan` defined in the `tradeplan.toml` file) are
associated to a `batch-id`. This is important when
analysing a trading day, or back-testing. When you back-test,
you re-run a batch-id, simulating market condition while
applying changes to the strategies being used.

**Note**: If a trading session is interrupted, the next run of
the `trader` application will check for current open
positions. If they exist, the trades done at the earlier session will be
relocated to the new session - this is done in order to
simplify trade session analysis. See the Analysis section
for more information.

Off-hours
*********
Once the day-trading ends, and all processes (scanners, consumers and producer) are done, off-hour tasks will run.

Currently supported tasks include:

* `gain_loss` : Populating `gain_loss` and `trade_analysis` DB tables with aggregated results per symbol, per algo_run_id.



Usage
*****

To run the trader app type:

.. code-block:: bash

    trader

An expected beginning of execution should look like:

.. image:: /images/trader-usage1.png
    :width: 600
    :align: left
    :alt: *trader* output


Understanding *trader* output and Logging
*****************************************

The *trader* application writes output to STDOUT
(standard output). It will also send
logging to `google-cloud-logging` if configured.
To learn more about how to configure
this feature read
the `How to Install & Setup` section.

The *trader* application uses a producer-consumers
design patterns. In other words, when executed the
scanners would run according to the specifications in `tradeplan`,
and then a single producer process
will spawn and a collection of consumer processes.
To understand the inner workings
read the `Concepts` section.

The *trader* application writes log outs in sections
to help troubleshooting and for better readability.

- The first section presents the filename being executed (`trader` in most cases) followed by a unique-id (GUID) which represents the trading session. Each time the `trader` application is run, a new batch-id will be created. To understand more read the `How to analyze your trades` section.
- The second section displays non-secure environment variables that may affect the trading behaviour. You should see the DSN (database connection string) properly displayed, and when you don't that's normally a sign that the env variables were not properly set.
- The third section displays the location of the `tradeplan` file and parses its header. A basic validation of the `tradeplan` file is done during that point and error messages will be presented for crude formatting.
- The fourth section normally displays the scanner execution. For more details on scanners read the `Scanners` section.
- The fifth and last section displays the strategies execution. For more details on strategies read the `Strategies` section.





