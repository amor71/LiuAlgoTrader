.. _`How to analyze your trades`:

Analyze your trades
===================


.. # define a hard line break for HTML
.. |br| raw:: html

   <br />

**Complete documentation in release 0.0.36**

LiuAlgoTrader comes equipment with a jupyter notebook
for analysing recent trades. This section explains how
to operate and make use of the analysis notebook in order
to imrpvoe your trading strategies.

Analyze *trader* session
------------------------

Prerequisites
*************

1. Make sure that the `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` environment variables are properly set and include the authentication data to your account (can be either PAPER or LIVE).
2. Make sure you know your DSN connection string.
3. Download the latest version of trading day analysis notebook from here_.

.. _here:
    https://github.com/amor71/LiuAlgoTrader/blob/master/analyis_notebooks/portfolio_performance_analysis.ipynb

Usage
*****

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
    :width: 400
    :align: left
    :alt: how was my day

.. image:: /images/port-analysis-3.png
    :width: 800
    :align: left
    :alt: how was my bad day

|br|
4. Cell #15 (Toggle-Scroll recommended) is the main cell to analyze your strategy, for each traded stock, the cell would list the trades calculate their horizontal support & resistance levels as calculated up to that point of the trade, as well as present the details of the trade including a graphic summary:

.. image:: /images/port-analysis-4.png
    :width: 800
    :align: left
    :alt: how was my day

|br|
.. image:: /images/port-analysis-5.png
    :width: 800
    :align: left
    :alt: how was my bad day








