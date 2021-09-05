**Back-testing**
================

.. # define a hard line break for HTML
.. |br| raw:: html

   <br />

This section describes LiuAlgoTrader back-testing capabilities. 
The framework is equipped with two sets of tools:
basic browser-based UI (using `streamlit`) and more advanced 
command-line tool coupled with `jupter notebook(s)` for analysis.

No Liability Disclaimer
-----------------------
LiuAlgoTrader is provided with sample scanners and
out-of-the-box strategies. You may choose to use it,
modify it or completely disregard it - Regardless,
LiuAlgoTrader and its Authors bare no responsibility
to any possible loses from using LiuAlgoTrader,
or any of its derivatives (on the other hand, they
also won't share your profits, if there are any).

Liu approach to back-testing
----------------------------

While the framework was designed for high-performance real-time trading 
with dynamic scanning from the stock universe, the framework is equipped with
a full stack of back-testing features. 

LiuAlgoTrader framework provides two different approaches to back-testing:

- Given a day-trading session (which is represented by a `batch-id` UUID), replay the trading session on the scanned stocks, minute-by-minute while executing modified versions of the strategies. This is a very useful approach to debug & improve strategies while comparing results to a base-line. The replay can be narrowed to only traded stocks (from the scanned stocks), or even focus on a specific stock. The original day-trading session can be on a paper-account, or a live trading session,
- Run strategies over long period of time, on fixed scanners (e.g. similar to how Zipline operates). Back-testing can be done on minute or daily resolution,

Picking the right back-testing tools
************************************

Day-trading sessions allow running scanners repeatedly, over the universe of 
stocks and select stocks for trading. Strategies receive feeds of the selected 
stocks and decide how to act upon them. Swing-trading on the other hand do not 
act on second, or even minute resolutions. Back-testing entire trading days, 
second by second on the entire stock universe can be done, however it requires 
downloading massive amounts of data, and computation power and is
not available out of the box with the provided momentum scanner. For more details
on how to customize scanners to achieve such behavior, see the `Scanners` 
documentation page. 

 
Perfecting a day-trading strategy can be done by running LiuAlgoTrader framework 
on a paper-account, followed by back-testing using the replay approach. Such back-testing sessions allow improving strategies,
but are less effective on scanners.  

Swing-trading on selected stocks can be effectively done while back-testing
strategies over long period of data. For swing-trading it is less effective to
replay a specific trading-session, since the bigger picture matter more. 

Back-testing for Swing-trading is avalaible out of the box, and does not require
specialized scanners or hardware.

Word of caution
***************

Day-trading is hard, perfecting day-trading algorithms is harder.
When replaying a day-trading session try to be aware of over-fitting and
**hindsight bias**. Make it a habit to always re-run strategy modifications
on a large number of day-trading sessions, and avoid making alterations 
to fit to a specific less-successful trading day. The more you day-trade on a
paper-account, the more data you collect, which in turn make the back-testing 
more effective. Last but not least, make small incremental changes, each time 
on a single parameter and progress slowly.


*backtester* for Day-Trading
----------------------------

This sub-section focuses on the tools for re-running past trading sessions on
revised strategies.

The tool comes in two 'favours': command-line tool and a browser-based UI 
using `streamlit`. The functionality of both tools is not exactly the same, 
please read the details below.

**NOTE:** While the `trader` application acts on events per-second, 
the `backtester` application runs on per-minute data.

Prerequisites
*************
1. Installed and configured Liu Algo Trading Framework.
2. An existing *tradeplan.toml* at the folder where the trader application is executed. For more details on how to setup the trade plan configuration file, see  `How to Configure` section,
3. [Optional] The batch-id (UUID) of a trade session to replay.

Command-line tool
*****************

To run the `backtester` application type:

.. code-block:: bash

    backtester

Displays a high-level description of the tool, and it has different parameters.
The version you are running might have more options than what is shown below:

.. image:: /images/backtester1.png
    :width: 800
    :align: left
    :alt: *backtester* usage


If you had run a `trader` session  (or have used `liu quickstart` wizard) the
database should hold at least one batch-id.

To get a list of previous trading sessions, run:

.. code-block:: bash

    backtester batch --batch-list

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
specific batch-id. Use the `--strict` command-line option to limit the back-test session to
traded symbols.


Below is a sample output of a running `backtester batch`:

.. image:: /images/backtester3.png
    :width: 800
    :align: left
    :alt: *backtester* sample run

|br|
|br|
**Notes**:

1. A back-test session creates a new `batch-id`. This is helpful when running analysis of a back-test session. See the Analysis section for more details.
2. Strategies running in a back-testing session are marked with `BACKTEST` environment when logging trades, this is helpful to distinguish between backtest trades, paper and live trades when querying the database.
3. When the `backtester` application starts, it lists all the stocks picked by the scanners during the trading session.
4. `backtester` re-runs each session, by loading per-minute candles for the stock trading session (up to one week back). This replay simulates per-minute trading, vs. per-second trading during `trader` execution (though the `trader` application can also be configured to execute strategies per minute and not per second).
5.  `backtester` supports a debug mode, per symbol. The debug flag is passed to the implementation for `Strategy.run()`, allowing more verbose logging during back-testing.

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
| strict         | This option limits the back-tested symbols to         |
|                | those that were actually traded during a session.     |
|                | The option is helpful to speed up back-test run       |
|                | during initial strategy development or improvement    |
|                | session.                                              |
+----------------+-------------------------------------------------------+
| duration       | The option over-rides the initial duration specified  |
|                | in the back-tested `tradeplan`. The option is less    |
|                | relevant for tradeplans with multiple trade windows.  |
+----------------+-------------------------------------------------------+
| debug          | When a symbol is selected for debugging, pass this    |
|                | flag as `True` for the `Strategy.run()` method.       |
|                | Based on the strategy implementation,                 |
|                | additional log may be provided.                       |
+----------------+-------------------------------------------------------+


Browser-base tool
*****************

If you used `liu quickstart` wizard or watched the intro video_, you've already seen
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

The browser-based UI supports two types of back-testing sessions:

1. Re-running strategies for a specific trading session. Similarly to the command-line tool,
2. Re-running strategies on a past date, **even if no past trading session took place on that date**. This capability is not yet exposed on the command-line tool.

**IMPORTANT NOTES**

1. When selecting the "`back-test against the whole day`" option , **scanners** will be called with a `back-time` schedule (vs. real-time),
2. Scanners are expected to support running in `back_time` mode (see scanners section).
3. The built-in scanner supports back-time mode - if no data exists in the database for that specific date, the framework would download OHLC data for all traded stock on the select date, and the day before. Please note that this process may take between minutes to couple of hours (on-time) depending on your network connection & equipment.
4. Instead of having the scanners trigger downloading of data, it is advised to use the `market_miner` tool to pre-load data in off-hours before running a back-test session on a day without any data.

To see an example of the tool, refer back to `liu quickstart` guide.

Analysis using the browser based tool
*************************************

While the browser-based tool is less configurable than the
command-line alternative, it does include a basic analysis 
tool for visualizng day-trading sessions. Select the `analyzer`
app on the app selector drop-box and enter a batch-id to visualize. 

Id you have used `liu quickstart` before, you should have the
batch-id "2398380c-5146-4b58-843a-a50c458c8071" available in your
database. 

*backtester* for Swing-Trading
------------------------------

Back-testing over large period of time is simple to execute. Once it is run a new `batch-id` will be generated, allowing analysis for the strategy behaviour.


Prerequisites
*************
1. Installed and configured Liu Algo Trading Framework,
2. An existing *tradeplan.toml* at the folder where the trader application is executed. For more details on how to setup the trade plan configuration file, see  `How to Configure` section.

How-To Use
**********

To run the back-testing you need to specify a starting day. 
For example, assuming `tradeplan.toml` file is present:

.. code-block:: bash

    backtester from '2020-10-18'

would generate output similar to:

.. image:: /images/backtester4.png
    :width: 800
    :align: left
    :alt: *backtester* backtester period

Once run, both the browser-based UI (with `streamlit`) and any of the analysis notebook(s) explained in the Analysis documentation section can be used to analyze the trading session:

.. image:: /images/streamlit-2.png
    :width: 800
    :align: left
    :alt: *backtester* streamlit analyzer 

Understanding command-line parameters
*************************************

+----------------+-------------------------------------------------------+
| Parameter Name | Description                                           |
+----------------+-------------------------------------------------------+
| to             | The last day for calculating the back-testing.        |
|                | the date is provided in the format `YYYY-MM-DD`.      |
|                | The `to` date will be included in the back-testing    |
|                | session. If not specified, `today` is being used.     |
+----------------+-------------------------------------------------------+
| scale          | The time-scale for running the back-test.             |
|                | Allowed values are: day or minute. If not specified   |
|                | day will be used. Keep in mind that minute will       |
|                | take longer to run, but may be more realistic         |
|                | for your strategy.                                    |
+----------------+-------------------------------------------------------+
| scanners       | Comma-separated list of scanner names to be used in   |
|                | the back-testing session. The scanner names are       |
|                | read from the `tradeplan.toml` file. if not           |
|                | specified all scanners will be executed.              |
+----------------+-------------------------------------------------------+
| strats         | Comma-separated list of strategy names to be used in  |
|                | the back-testing session. The strategy names are      |
|                | taken from the `tradeplan.toml` file. if not          |
|                | specified all strategies will be executed.            |
+----------------+-------------------------------------------------------+
