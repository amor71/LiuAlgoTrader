.. _`Strategies`:

Strategies
==========

Developing a Strategy is core for using `LiuAlgoTrader` framework.

Assumptions
-----------
This section assumes the audience has:

1. Carefully read and understood the `Concepts` section,
2. Read the `Scanners` section and has a working setup of the framework with at least one Scanner.


No Liability Disclaimer
-----------------------
Any example, or sample is provided for training purposes only.
You may choose to use it, modify it or completely
disregard it - `LiuAlgoTrader` and its authors bare
no responsibility to any possible loses from using
a scanner, strategy, miner, or any other part of `LiuAlgoTrader` (on the other hand, they also won't
share your profits, if there are any).


The Basics
----------
* As with Scanners, each strategy should have it's own unique name,
* `LiuAlgoTrader` supports both *long* and *short* strategies,
* `LiuAlgoTrader` support two strategy types:

  +------------------+-----------------------------------------------+
  | Name             | Description                                   |
  +------------------+-----------------------------------------------+
  | DAY_TRADING      | Held positions will be automatically          |
  |                  | liquidated at the end of the trading day.     |
  +------------------+-----------------------------------------------+
  | SWING            | No automatic liquidation.                     |
  +------------------+-----------------------------------------------+

* The framework supports trading windows (=time frame for buying) per
  strategy out of the box, however they are not enforced.

* A Strategy may act on a single symbol, or can act on a collection of symbols (e.g. SP500)

Configuration
-------------
Strategies are declared in the *trade_plan* Database table, or in the *tradeplan.toml*
configuration file under the section:

.. code-block:: bash

    [strategies]

tradeplan.toml
**************

Strategies may run concurrently. The order
of execution is based on the order in which strategies are presented in the *tradeplan* file.

Each strategy should have its own entry point in the
`tradeplan.toml` configuration file. With `filename` pointing to the
full path to the python file containing the strategy to be executed,
and at least one trading window.

For example:

.. code-block:: bash

    [strategies]
        [strategies.MyStrategy]
            filename = "/home/liu/strategies/my_strategy.py"

            [[strategies.MyStrategy.schedule]]
                start = 15
                duration = 150

Trading windows are not enforced by the framework, the Strategy
developer may elect to ignore them.

Strategies are instantiated inside `consumer` processes, immediately
proceeding the creation of the scanners and producer processes.

A Strategy may have any number of parameters, once instanticated, the Framework will 
pass all the parameters from the `.toml` file to the strategy. 
Exception will be raised if parameters are missing. Always make sure to called
`super()` to ensure proper setting of basic parameters.

trade-plan table
****************
See *Concepts* section from further details

Developing a Strategy
---------------------

To inherit from the Strategy based class:

.. code-block:: python

    from liualgotrader.strategies.base import Strategy, StrategyType

Creating a strategy involves:

1. Declaring a class object, inherited from the `Strategy` base_ class,
2. Overwrite both the `__init__()` and `run()` functions. __init__() is called during initialization, and is passed the configuration parameters from the `tradeplan.toml` file.`run()` is called when the framework is ready to execute the scanner.

.. _base:
    https://github.com/amor71/LiuAlgoTrader/blob/master/liualgotrader/strategies/base.py

`__init__()` function
*********************

The `__init__()` function is called by the framework
with a **batch_id** and configuration parameters declared in the
configuration file. Declaring a trading window is a must, and
the framework will throw an Exception if they are not present.

The function is expected to call the base-class
`__init__()` function with a unique name, type
(e.g. swing or day trading) and trading window. Name and type are
normally static in the strategy object and not passed
from the configuration file.

Please review the base class for furthe details.

`run()` and `run_all()` functions
*********************************

`run()` is called per picked symbol, per event. That would normally mean at least once per second, 
per stock. `run_al()` is called once, every one minute, with list of all open positions and a
DataLoader. The Platform decides which function to call, based on the value returned by 
`should_run_all()`. See `base.py` for further details.


`run()` Actions
***************

The functions returns a tuple of a boolean and dictionary.
The functions may return one of the below combinations:

.. code-block:: python

    return False, {}

--> No action will be taken by the framework,

.. code-block:: python

    return True, {
        "side": "buy",
        "qty": str(10),
        "type": "limit",
        "limit_price": "4.4",
    }

--> Requesting the framework to execute a limit order for quantity 10 and limit price $4.4,

.. code-block:: python

    return True, {
         "side": "buy",
         "qty": str(5),
         "type": "market",
    }

--> Purchase at market. Similarly for **sell** side,

.. code-block:: python

    return False, {"reject": True}

--> Mark the symbol as `rejected` by the strategy, ensuring `run()` will not be called again with the symbol during this trading session.

`buy_callback()`
****************
Called by the framework post completion of a buy ask. Partial fills won't trigger the callback,
only the final complete will trigger. Partial trades will still be persisted on the database.

`sell_callback()`
*****************
Called by the framework post completion of the sell ask. Partial fills won't trigger the callback,
only the final complete will trigger.

Trading windows
***************
Trading windows are list of time-frames during which a strategy may look
for a signal to open positions. The framework does not enforce the
windows, but rather provides useful functions on the base class that may
be overwritten by the strategy developer.

`is_buy_time()`
^^^^^^^^^^^^^^^
This function, implemented by the Strategy base-class, looks at the configured
schedule and will return `True` if current time is over `start` minutes
from the market open and below `start`+`duration` time from market open.

`is_sell_time()`
^^^^^^^^^^^^^^^^
Returns `True` if at least 15 minutes passed since the market open, AND the buy window elapsed.

It is up to the Strategy developer if to use these functions or not.

Data Persistence
****************
`LiuAlgoTrader` framework stores successful
operations. This data serves well the analysis tools provided by the
framework.

Aside from an Notebooks and Streamlit applications for analysis,
the framework automatically calculates gain & loss per per strategy,
per buy-sell (or sell-buy) operations. Calculations are done in price change value,
percentage and also `r units`. Once enough data is collected, the framework
will feedback probability estimate, in real-time, for a strategy based
on Machine-Learning models calculated by the framework.

For this purpose, the strategy developer is ask to fill 4 **Global Variables**:

.. code-block:: python

    from liualgotrader.common.trading_data import (
        buy_indicators,
        sell_indicators,
        stop_prices,
        target_prices,
    )

* stop_prices[symbol] = <selected stop price>
* target_prices[symbol] = <selected target price>
* buy_indicators[symbol] is dictionary persisted as JSON including the strategy indicators and reasoning for buying.
* sell_indicators[symbol] is dictionary persisted as JSON including the strategy indicators and reasoning for selling.

The variables can be left out (some strategies, simply do not have stop
prices) though its highly recommended to have them included.


Example
-------
Putting it all together in a generic Strategy:

.. literalinclude:: ../../examples/skeleton-strategy/my_strategy.py
  :language: python
  :linenos:

Sample `tradeplan.toml` configuration file:

.. literalinclude:: ../../examples/skeleton-strategy/tradeplan.toml
  :language: bash
  :linenos:



Behind the scenes
-----------------
Actually a lot is happening behind the scenes! upon setting up the
scanner and producer processes, consumer processes are spawned.
The number of processes is either pre-determined by an environment
variable, or estimated based on the OS & hardware capabilities.

When the consumer processes are spawned, the existing profile in Alpaca is
examined to try and figure if the `trader` app crashed and strategies
should resume. Once existing positions are loaded, they are matched with
instantiated strategies, events of picked stocks start to pour and the `run()`
functions are called.

Once a strategy decides to purchase a symbol,
the framework will place the buy (or sell) order with
Alpaca, start follow it and persist the
transactions to the `new_trades` table. Both partial and complete orders are stored, and tracked.

If an update for a strategy operation is not received within a
pre-configured windows of time (default is 60 seconds), the framework
will check if the order was completed w/o a notification, and if so,
will simulate a complete event. However if the operation did not
conclude, it will be cancelled, and open order will be cleared, and the
strategy may re-trigger an operating based on signals.

The framework works behind the scenes to free the
strategy developer from worrying about broker
(Alpaca.Markets) and data provider (Polygon.io) integrations.

Global Vars
***********
While each strategy may keep track of it's own variables,
the framework is tracking global variables. The variables
can be access by importing **liualgotrader.common.trading_data** module.

Parameters include:

+----------------------+----------------------------------------------------------+
| Parameter            | Description                                              |
+----------------------+----------------------------------------------------------+
| open_orders          | dictionary, with `symbol` as index and holdin a tuple    |
|                      | Order object w/ "buy" or "sell" side.                    |
+----------------------+----------------------------------------------------------+
|open_order_strategy   | dictionary, with `symbol` as index and holding reference |
|                      | to the Strategy w/ an open order.                        |
+----------------------+----------------------------------------------------------+
| buy_time             | dictionary, with `symbol` as index and datetime object   |
|                      | of order request time in EST.                            |
+----------------------+----------------------------------------------------------+
| minute_history       | dictionary, with `symbol` as index and DataFrame with    |
|                      | OHLC, Volume, vwap and average, per minute.              |
+----------------------+----------------------------------------------------------+
| positions            | dictionary of open positions.                            |
+----------------------+----------------------------------------------------------+
| last_used_strategy   | dictionary w/ reference to last strategy with completed  |
|                      | order, per symbol.                                       |
+----------------------+----------------------------------------------------------+

**IMPORTANT NOTE**:

The global variables are there for a purpose: suppose you run two strategies
in parallel, both `run()` functions would be hit with symbol events.
Let's assume you hold a position in the symbol. One strategy may identify a sell
signal, while the other does not. Depending on the strategy combination and
architecture, it might be wise for a strategy to confirm it was actually
the one initiating the original buy by consulting **last_used_strategy[symbol]**

Key-store
*********

The platform implement a key-value store, per strategy (see base.py for implementation details). 
key-value allows for strategies to persist state across executions. 
This feature is specifically helpful for `swing` strategies that run across different batches. 


Additional Configurations
^^^^^^^^^^^^^^^^^^^^^^^^^

`LiuAlgoTrader` framework has quite a few knobs & levers to
configure the behaviour of the platform and the strategies.

The best place to check out all possibilities is here_.

.. _here:
    https://github.com/amor71/LiuAlgoTrader/blob/master/liualgotrader/common/config.py

Some of the configurations are documented in the tradeplan.toml file,
some are in environment variables, and some may be over-written by the
strategy developer.

