Samples
-------


Mama-Fama Strategy
==================



The folder_ includes a real-life example of `LiuAlgoTrader` usage.

**NOTE**: The samples in this folder require installation of TA_LIB_ (specifically, see notes for Windows users).


.. _TA_LIB: https://github.com/mrjbq7/ta-lib

.. _folder:
    https://github.com/amor71/LiuAlgoTrader/tree/master/examples/mama-fama

**Step 1**: off-hours calculations


1. Make sure you have installed and configured LiuAlgoTrading Framework.
2. Ensure all environment variables are properly setup, specifically the database DSN, and the Alpaca API credentials,

3. Execute `market_miner` application using the sample `miner.toml` file. The `market_miner` application will populate the database with OHCL & MAMA/FAMA daily signals for the past 60 days.


**Step 2**: execute the strategy

During market hours, and assuming `LiuAlgoTrader` is properly setup execture the `trader` application using the supplied `tradeplan.toml`.
