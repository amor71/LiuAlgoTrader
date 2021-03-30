**Off-market**
==============

.. # define a hard line break for HTML
.. |br| raw:: html

   <br />


No Liability Disclaimer
-----------------------
LiuAlgoTrader is provided with sample scanners and
out-of-the-box strategies. You may choose to use it,
modify it or completely disregard it - Regardless,
LiuAlgoTrader and its Authors bare no responsibility
to any possible loses from using LiuAlgoTrader,
or any of its derivatives (on the other hand, they
also won't share your profits, if there are any).

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

.. literalinclude:: ../../examples/miner.toml
  :language: python
  :linenos:

miners
******

Currently supported miners:


- `StockCluster` : the miner read all trade-able stocks, and stores in the `ticker_data` table the industry/segment and similar stocks details. This data can later be used in real-time to compare how a certain stock is doing against an industry/segment or similar stocks index.
- `gainloss`: populate `gainloss` table w/ per batch aggregated P&L details.

**Notes**

1. The `market_miner` app should be executed in off-hours, and once run it will refresh existing data, or load data since last run,
2. Additional miners can be found in the examples_ folder (and should be downloaded separately),

.. _examples:
    https://github.com/amor71/LiuAlgoTrader/tree/master/examples


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


