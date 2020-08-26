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


trader
------

market_miner
------------

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



