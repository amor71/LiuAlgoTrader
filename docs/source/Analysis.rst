.. _`How to analyze your trades`:

Analyze your trades
===================

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

The steps  to run the notebook are:

1. Select the relevant date range on the cell #2 (`start_day_to_analyze`, `end_day_to_analyze`),
2. Confirm the DSN is correctly setup on cell #3.
3. Select `Restart & Run All`








