How To Use
==========

LiuAlgoTrader exposes three applications and a set of
analysis notebooks.

The applications are:

- *market_minder.py*
- *trader.py*
- *backtester.py*


This section describes the three applications,
while the notebooks are described in the `Analysis` section.

market_miner
------------

Prerequisites
*************

1. Installed & configured `PostgreSQL` instance, hosting a database w/ LiuAlgoTrader schema,
2. Ensuring environment variables are properly set including Alpaca Market API credentials, and the database DSN,

Usage
*****

To run the market_miner app type:

.. code-block::

    python liualgotrader/market_miner.py

The expect result should look like:

.. image:: /images/market-miner-usage.png
    :width: 600
    :align: left
    :alt: *market_miner* output


trader
------

backtester
----------



