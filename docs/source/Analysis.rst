Liu Analysis Tool-box
=====================

`LiuAlgoTrader` is equipment with jupyter notebooks_
for analysing portfolio, trader, and back-testing sessions.

.. _notebooks:
    https://github.com/amor71/LiuAlgoTrader/blob/master/analysis/notebooks/portfolio_performance_analysis.ipynb

.. # define a hard line break for HTML
.. |br| raw:: html

   <br />

prerequisites
-------------

1. Both `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` environment variables should be properly set and include the credentials to Alpaca Markets account (can be either PAPER or LIVE),
2. Environment variable `DSN` holds valid DB connection string,

Anchored-VWAP Notebook
----------------------

The `anchored vwap`_ analysis notebook calculates and visualizes anchored vwaps on top of an interactive stock candlestick diagram, with volume .

.. _anchored vwap:
    https://github.com/amor71/LiuAlgoTrader/tree/master/analysis/notebooks/anchored-vwap-lab.ipynb

prerequisites
*************
if you do not have `pyplot` installed:

.. code-block:: bash

   pip install pyplot

running the notebook
********************

once loaded, the top of the notebook looks like:


.. image:: /images/anchored-1.png
    :width: 1000
    :align: left
    :alt: anchored vwap top of notebook


The list `anchored_vwaps_start` holds start timestamps for anchored VWAPs, per `symbol` between the `start_date` and `end_date`.

Once executed, the output generated includes an interactive candlestick diagram including the selected anchored VWAPs:

.. image:: /images/anchored-2.png
    :width: 1000
    :align: left
    :alt: anchored vwaps example



Tear Sheet Notebook
-------------------

The `tear sheet`_ analysis notebook provide basic means to analyze your portfolio performance over time.

.. _tear sheet:
    https://github.com/amor71/LiuAlgoTrader/tree/master/analysis/notebooks/tear_sheet.ipynb

The top of the notebook looks like:

.. image:: /images/returns_notebook_1.png
    :width: 1000
    :align: left
    :alt: liu returns analysis

The cell holds the two configurable parameters:

1. `env`: the portfolio environment to analyze. Values can be PAPER, PROD, or BACKTEST
2. `start_date`: a string representing the initial date from when to run the analysis.

Once executed, the notebook is made of 3 parts:

1. **Revenue & Percentage per strategy**: analysis of revenues over time per strategy, and for the entire portfolio. Graphs are shown in two columns, the left column shows the $ value, while the right column shows the daily percentage changes.

.. image:: /images/returns_notebook_2.png
    :width: 1000
    :align: left
    :alt: liu returns analysis

2. **Accumulative Revenue & Draw-down**: accumulative revenue per strategy, including daily draw-down graph (volatility).

.. image:: /images/returns_notebook_3.png
    :width: 1000
    :align: left
    :alt: liu returns analysis

3. **Strategy performance distribution**: analysis of portfolio distribution, showing summary of mean, std as well as skew and kurtosis (3rd and 4th moments), and histograms.

Analyze a *trader* session
--------------------------

When the notebook opens up you should see a screen similar to:

.. image:: /images/port-analysis-1.png
    :width: 800
    :align: left
    :alt: analysis top

|br|
The steps  to run the notebook are:

1. Select the relevant date range on the cell #2 (`start_day_to_analyze`, `end_day_to_analyze`),
2. Confirm the DSN is correctly setup on cell #3.
3. Select `Restart & Run All`

Notebook rundown
****************

1. Cell #6 will present the DataFrame including all trades (including partial fills) taken during the selected time frame.
2. Cell #8 will list execution of strategies *per process* done during the time frame.
3. Cell #14 will list all the symbols traded during the time-frame, including the number of trades, and the $ value per stock symbol, as well as a profit/loss summary for the time-frame **per trading session** :


.. image:: /images/port-analysis-2.png
    :width: 200
    :align: center
    :alt: how was my day

|br|
|br|

.. image:: /images/port-analysis-3.png
    :width: 800
    :align: center
    :alt: how was my bad day

|br|
|br|

4. Cell #15 (Toggle-Scroll recommended) is the main cell to analyze your strategy, for each traded stock, the cell would list the trades calculate their horizontal support & resistance levels as calculated up to that point of the trade, as well as present the details of the trade including a graphic summary:

.. image:: /images/port-analysis-4.png
    :width: 800
    :align: left
    :alt: trade run down

|br|
|br|

.. image:: /images/port-analysis-5.png
    :width: 600
    :align: left
    :alt: trade graphics

|br|
|br|

**Notes**:

1. The graph shows buy trades in green, and sell in red
2. green horizontal lines are at support levels, red on resistance
3. The indicators column displays whatever JSON is submitted as buy or sell indicators returning from the `Strategy.run()` function.

|br|



Analyze *backtester* session
----------------------------

Prerequisites
*************

1. Make sure that the `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` environment variables are properly set and include the authentication data to your account (can be either PAPER or LIVE).
2. Make sure you know your DSN connection string.
3. Download the latest version of backtester analysis notebook_.

.. _notebook :
    https://github.com/amor71/LiuAlgoTrader/blob/master/analysis/notebooks/backtest_performance_analysis.ipynb

Usage
*****

Using the `backtester` notebook is similar to using
the `trader` notebook, with the difference of entering
the backtester `batch-id` instead of the time-frame
as with the `trader` notebook.




