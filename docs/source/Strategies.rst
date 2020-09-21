.. _`Strategies`:

Strategies
==========

`LiuAlgoTrader` comes equipped with a **momentum** strategy,
which is based on `MACD signals`_ enforced with RSI_ and LOB imbalance signals.

.. _`MACD signals`:
    https://www.investopedia.com/terms/m/macd.asp

.. _RSI:
    https://www.investopedia.com/terms/r/rsi.asp

You can easily extend the available strategies,
by inheriting from the *Strategy* base class as explained below.

Notes for strategy developers
-----------------------------
1. `LiuAlgoTrader` supports both *long* and *short* strategies: short buy returns sell w/ positive quantity while short sell returns buy with positive quantity.
2. Each strategy may have a collection of schedule windows as part of the TOML `tradeplan` file. It is the responsibility of the strategy and **not** `LiuAlgoTrader` framework to enfroce the trading windows.


No Liability Disclaimer
-----------------------
The *momentum-strategy* is provided as a sample strategy,
You may choose to use it, modify it or completely
disregard it - `LiuAlgoTrader` and its authors bare
no responsibility to any possible loses from using
the strategy, or any other part of `LiuAlgoTrader` (on the other hand, they also won't
share your profits, if there are any).

Momentum Strategy Sample
------------------------
Strategies are defined in the *tradeplan.toml* TOML
configuration file under the section:

.. code-block:: bash

    [strategies]


Note that several Strategies may run, yet the order
of execution is based the order presented in the *tradeplan* file.


The **[strategies.MomentumLong]** section lists the momentum strategy
properties:

+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| check_patterns   | Use candle-stick patterns for sell signals    |
|                  | this is false by default.                     |
+------------------+-----------------------------------------------+


The strategy (as any strategy you will develop
yourself) supports several execution windows under
the subsection

.. code-block:: bash

    [strategies.MomentumLong.schedule]


The schedule properties are:

+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| start            | The number of minutes, since start of the     |
|                  | trading day, to start buying and selling.     |
+------------------+-----------------------------------------------+
| duration         | The number of minutes, since the beginning of |
|                  | the strategy execution, to stop buying new    |
|                  | stock.                                        |
+------------------+-----------------------------------------------+

Custom Strategy
---------------
Creating your own custom strategy is as easy as
inheriting from the Strategy class, and implementing
the *run()* function which returns the selected stock symbols.

`LiuAlgoTrader` support different strategy types:


+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| DAY_TRADING      | Transaction will be automatically liquidated  |
|                  | by end of                                     |
+------------------+-----------------------------------------------+
| SWING            | No automatic liquidation                      |
+------------------+-----------------------------------------------+



Here is an example of *my_strategy.py*:

.. literalinclude:: ../../examples/my_strategy.py
  :language: python
  :linenos:

Configuring the custom strategy in the *tradeplan* TOML file is as easy:

.. literalinclude:: ../../examples/tradeplan.toml
  :language: bash
  :linenos:

While executing, the **trader** application will look for *my_strategy.py*,
instantiate the `MyStrategy` class, and call it with the arguments defined
in the `tradeplan` configuration file, while adding the trade-api object.


Building a winning strategy
---------------------------

`LiuAlgoTrader` framework comes with a lot of tools
and capabilities which constantly evolve.
In order to write a winning strategy that
goes beyond the basic sample presented here,
it is best advised to go through the `under the hood`
section to understand how to re-use the framework
capabilities.

Hey, if you created an awesome strategy,
please share it with the rest of the community!











