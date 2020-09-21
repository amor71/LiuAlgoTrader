Samples
-------


Mama-Fama Strategy
==================



The folder_ includes a real-life example of `LiuAlgoTrader` usage.

.. _folder:
    https://github.com/amor71/LiuAlgoTrader/tree/master/examples/mama-fama

**Step 1**: off-hours calculations


1. Make sure you have a database setup for usage w/ `LiuAlgoTrader`. Details for setting up a docker can be found here: https://github.com/amor71/trade_deploy run the `market_miner` application,

2. Ensure all environment variables are properly setup, specifically the database DSN, and the Alpaca API credentials,

3. Execute `market_miner` application using the sample `miner.toml` file. The `market_miner` application will populate the database with OHCL & MAMA/FAMA daily signals for the past 60 days.


**Step 2**: execute the strategy

During market hours, and assuming `LiuAlgoTrader` is properly setup execture the `trader` application using the supplied `tradeplan.toml`.
