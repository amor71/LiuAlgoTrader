.. _`Scanners`:

Scanners
========

As explained in the `Concepts` section, scanners scan the stock universe for stocks of interest.
When the `trader` application starts, it reads the `tradeplan.toml` file, looks at the **[[scanners]]** section to identify which scanners needs to be instantiated and executed. Scanners are initially executed by the order of appearance in the `tradeplan` file. The framework comes equipped with a generic, momentum scanner, but it should mostly be used as a reference when designing your own scanners.

Some configuration parameters are generic to all scanners, and some may be specific for your own scanner.

No Liability Disclaimer
-----------------------
Any example, or sample is provided for training purposes only.
You may choose to use it, modify it or completely
disregard it - `LiuAlgoTrader` and its authors bare
no responsibility to any possible loses from using
a scanner, strategy, miner, or any other part of `LiuAlgoTrader` (on the other hand, they also won't
share your profits, if there are any).

Developing a Scanner
--------------------

When developing your scanner, you will first need to import the Scanner base-class:

.. code-block:: python

   import alpaca_trade_api as tradeapi
   from liualgotrader.scanners.base import Scanner

Creating a scanner involves:

1. Declaring a class object, inherited from  the`Scanner` base_ class,
2. Overwrite both the `__init__()` and `run()` functions. __init__() is called during initialization, and is passed the configuration parameters from the `tradeplan.toml` file. The `run()` is called when the framework is ready to execute the scanner.

.. _base:
    https://github.com/amor71/LiuAlgoTrader/blob/master/liualgotrader/scanners/base.py

The `__init__()` function
*************************

A Generic implementation for the `__init__()` function:

.. code-block:: python

    def __init__(self, recurrence: Optional[timedelta], data_api: tradeapi, **args):
        print(args)
        super().__init__(
            name=self.name,
            recurrence=recurrence,
            data_api=data_api,
            target_strategy_name=None,
        )


The run() function
******************

The `run()` function is the heart of the Scanner. The skeleton implementation:

.. code-block:: python

    async def run(self, back_time: datetime = None) -> List[str]:


The run() function returns the list to stock symbol which the framework needs to start tracking. back_time is used by the `backtester` to simulate past time-stamps allowing for the scanner developer to test various scenarios before deployment.

.. code-block:: python

    self.data_api

Holds the Alpaca.Markets tradeapi to be used for querying the stock universe. Refer to the Alpaca API documentation to learn more of its usage. Note that since the framework is dependent on the API, it will be automatically installed when you install the framework. It is recommended that that you pull up the **momentum scanner** implementation code as a good starting point, some examples can be found in the `examples` folder too.

Behind the scenes
*****************
As a developer, I hate 'magic' that happens without my understanding, hence it's important for me to detail the inner workings of the framework. All scanners run inside a dedicated process. When the process is executed, it receives the scanner portion of the configuration files, and creates an `asyncio` task per scanner. In fact, it's up to the scanners to make sure they play along nicely and not starve each other with overly long calculations.

The scanner task, wraps the scanner object, it executes the `run()` function, retrieves the list of picked stocks and transmits them over a Queue to the `producer` process. The task, would then `sleep()` for the duration of the `recurrence` parameter (or just run once, if that parameter is not present).

The producer would receive the list of picked symbols, it will register them for events on the `Polygon.io` data-stream, and will persist to the database the timestamp of receiving a picked stock. This data is then used by the `backtester` application to replicate the real conditions presented to a Strategy.

Example
*******

An example of *my_scanner.py*:

.. literalinclude:: ../../examples/scanners/my_scanner.py
  :language: python
  :linenos:


Configuring the custom scanner in the *tradeplan* TOML file is as easy:

.. code-block:: none

    [scanners]
        [scanners.MyScanner]
            filename = "my_scanner.py"

            my_arg1 = 30000
            my_arg2 = 3.5

While executing, the **trader** application will look for *my_scanner.py*,
instantiate the `MyScaner` class, and call it with the arguments defined
in the `tradeplan` configuration file, while adding the trade-api object.

Advanced
********

Scanners can "direct" symbol picks to a specific strategy. To direct symbol picks, include `target_strategy_name` in the configuration file. That parameter, if present, will be passed along from the scanner process to the producer process, and later to the consumer process to make sure only the relevant strategy receives the pick.

Normally, the producer subscribes to all Polygon.io available events per picked stock. However, to improve performance, if the strategies do not make use of per-second events, or quotes or trades, it's recommended to select only the relevant events in the configuration file:

.. code-block:: bash

    events = ["second", "minute", "trade", "quote"]

Lastly, if configuration parameter `test_scanners` is set to `true`. The `trader` appliction will only execute the scanners w/o running strategies to assist in the debugging process of a new scanner.



Momentum Scanner
----------------
Scanners are defined in the *tradeplan.toml* TOML
configuration file under the section **[[scanners]]**. Note that
several Scanners may run, at different schedules and
identify new stocks that needs to be fed into the Strategies
pipeline.

The **[scanners.momentum]** momentum scanner has several
properties:

+------------------+-----------------------------------------------+
| Name             | Description                                   |
+------------------+-----------------------------------------------+
| provider         | stock data provider: *polygon*, *finnhub*     |
+------------------+------------------------+----------------------+
| min_volume       | scan for tickers with minimal volume since    |
|                  | day start                                     |
+------------------+-----------------------------------------------+
| min_gap          | tickers gaping up in percentage (e.g. 3.5)    |
+------------------+-----------------------------------------------+
| min_last_dv      | minimum last day dollar x volume              |
+------------------+-----------------------------------------------+
| min_share_price  | minimum stock price                           |
+------------------+-----------------------------------------------+
| max_share_price  | maximum stock price                           |
+------------------+-----------------------------------------------+
| from_market_open | number of minutes to wait, since market open  |
|                  | before starting to scan from relevant stocks  |
+------------------+-----------------------------------------------+
| max_symbols      | max number of symbols to scan for             |
+------------------+-----------------------------------------------+
| recurrence       | frequency of re-running scanner, if not       |
|                  | present, run only once                        |
+------------------+-----------------------------------------------+

**Notes**

- When using Finnhub, since there is currently no way to get a full view of the market, it's best advised to use the max_symbols property, at lower numbers, unless you have access to a paid Finnhub account without API throttling.
- Unless otherwise specified, the trader applications scans & trades a limited number of stocks, however that limitation may be overwritten using **LIU_MAX_SYMBOLS** env variable.


Scanners in back-test application
*********************************

The scanners `run()` function receives a datetime
parameter **back_time**. The parameter is used when
called from the backtester when the
"`back-test against the whole day`" option is used.

Scanners are expected to support this mode by querying
past data from the database, if such data is present, or pull the past data from Polygon.io.
Sample_ implementation can be found

.. _Sample:
    https://github.com/amor71/LiuAlgoTrader/blob/master/liualgotrader/scanners/momentum.py#L270


