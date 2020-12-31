Examples
========

No Liability Disclaimer
-----------------------
Any example, or sample is provided for training purposes only.
You may choose to use it, modify it or completely
disregard it - `LiuAlgoTrader` and its authors bare
no responsibility to any possible loses from using
a scanner, strategy, miner, or any other part of `LiuAlgoTrader` (on the other hand, they also won't
share your profits, if there are any).


Momentum Swing Trading
----------------------
Inspired by Andrew Clenow's Book `Stocks On The Move`_ :

.. _`Stocks On The Move`:
    https://www.followingthetrend.com/stocks-on-the-move/

* A miner_ calculating Stock Momentum portfolio (base be used for rebalancing portfolio, and position size),
* A miner.toml configuration_ file, to be used with the framework `market_miner` calculating a portfolio based on the momentum strategy,
* Portfolio Analysis notebook_ for viewing miner portfolio calculation results,
* SP500_ analysis notebook.

.. _miner:
    https://github.com/amor71/LiuAlgoTrader/blob/master/examples/swing_momentum/portfolio.py

.. _configuration:
    https://github.com/amor71/LiuAlgoTrader/blob/master/examples/swing_momentum/miner.toml

.. _notebook:
    https://github.com/amor71/LiuAlgoTrader/blob/master/analysis/notebooks/momentum_portfolio.ipynb

.. _SP500:
    https://github.com/amor71/LiuAlgoTrader/blob/master/analysis/notebooks/indices.ipynb



Generic Strategy Example
------------------------

This example (also presented in Strategies section) presents a generic Strategy template.

.. literalinclude:: ../../examples/skeleton-strategy/my_strategy.py
  :language: python
  :linenos:


Mama-Fama Strategy
------------------


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
