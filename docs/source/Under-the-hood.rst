.. _`Understanding what's under the hood`:


Under the hood
==============

This section explain the inner working of LiuAlgoTrader. It may be used to developer who wish
query LiuAlgoTrader database directly, optimize the application
for their specific setup, or contributing to
the on-going development of LiuAlgoTrader.

Hands-free framework
--------------------

LiuAlgoTrader is designed to allow trading of as many stocks
with as many events as possible given limited hardware
capabilities.

It is designed to be communications hands-free framework
for strategy developers, elevating the need to worry about
communication disconnects or understanding of low level
considerations specifically in a language like Python which
is not high throughput in nature.


Understanding the multiprocessing approach
------------------------------------------

Why multi-processing?
*********************

Polygon.io and the other real-time stock data
providers are using WebSockets_ to send data. In most cases
data providers become impatient when posted data is not
collected by the intended recipient on a timely manner.

LiuAlgoTrader implements a producer-consumer
design pattern, where a single process interacts with the
data provider, and several consumer processes are handling
the algorithmic decision making and make API calls to initiate
trades.

Implementation details
**********************

LiuAlgoTrader is implemented using Python 3.8.x `multi-process
infrastructure`_, and each process uses `asyncio` for
inter-process lightweight threading. This architecture
provides high throughput which maximizes the hardware
capabilities.

Each consumer has a designated cross-process Queue and a
pre-defined list of stocks that the process is tracking.
The producer's role is to receive updates over the WebSocket,
post them into the relevant consumer's Queue, and return to
process the next incoming message.

Each consumer reads events from the Queue, parses them the
calls the strategies selected in the `tradeplan` configuration
file.

Upon running the `trader` application, scanners would run and
stock would be picked. Based on the number of stock, and the
available CPUs consumer processes would be spawn. As they
start, the producer process is spawned, and the communication
with the data-stream provider is initiated.

Performance
***********

Each consumer would check the time-stamp on the received events.
If the events are more than 5 seconds old, the message will be
disregarded, and the consumer queue would be cleaned.
This allows a quick catch-up on the expense of losing data.
When such catch-up takes place the following message would
be written to the log:

.. code-block:: bash

    consumer A {symbol} out of sync w {time_diff}

When you see such a message repetitively, it may mean that either:

- The Strategy being used takes too long to calculate compared to the number of stocks handled by that single process. It will be a good idea to double-check the Strategy code, and check if performance improvements are possible,
- It is possible that the Strategy writes to much to the log causing delays,
- The number of stocks traded is too high of the hardware setup. In that case it would be best to reduce the max number of stocks (environment variable)
- The consumer process listen to second message, as well as trade and quote messages, depending on the strategy and hardware capacity it might be best to reduce the event types that the producer is sending to the consumers (change the `tradeplan` configuration file),


.. _WebSockets :

    https://en.wikipedia.org/wiki/WebSocket#:~:text=WebSocket%20is%20a%20computer%20communications,WebSocket%20is%20distinct%20from%20HTTP.

.. _multi-process infrastructure :
    https://docs.python.org/3/library/multiprocessing.html


Understanding the project structure
-----------------------------------

Understanding the project structure is the first step in
uncovering the tools available to the custom strategy
developer. Below is the project
structure highlighting important
files for a future developer.

::

    ├── AUTHORS
    ├── LICENCE
    ├── analysis_notebooks
    │   ├── portfolio_performance_analysis.ipynb
    │   └── backtest_performance_analysis.ipynb
    ├── liualgotrader
    │   ├── common
    |   |   ├── config.py
    |   |   ├── market_data.py
    |   |   ├── tlog.py
    |   |   └── trading_data.py
    │   ├─── data_stream
    |   |    ├── alpaca.py
    |   |    └── streaming_base.py
    │   ├── fincalcs
    |   |    ├── candle_patterns.py
    |   |    ├── support_resistance.py
    |   |    └── vwap.py
    │   ├── models
    |   |    ├── algo_run.py
    |   |    └── new_trades.py
    │   ├── scanners
    |   |    ├── base.py
    |   |    └── momentum.py
    │   ├── strategies
    |   |    ├── base.py
    |   |    └── momentum_long.py
    │   ├── consumer.py
    │   └── polygon_producer.py
    ├── examples
    ├── tools
    └── tests

common
******
The common folder contains three important files that the developer should be aware of:

- `config.py` this is a global configuration file. The file includes internal constant which are no accessible via the environment variables of the configuration file for now.
- `tlog.py` is a simple log implementation which write log entries both to STDOUT, as well as GCP *stackdriver* logger, if it is configured.
- `trading_data` includes global variables that are shared between the strategies and the consumer infrastructure. This file should be viewed in details to understand data passing.

fincalcs
********
The folder includes packages for basic financial calculations.
Those are helper functions for strategy developers:

- `candle_patterns.py` - implements basic candle patterns
- `support_resistance.py` - implements basic algorithms for calculations of horizontal support and resistance lines.
- `vwap.py` - accuratly calculation 5-min VWAP, helpful for VWAP based strategies.

models
******
Data abstraction layer implementing the persistence and loading of the data model.

Data Model
----------

**Complete documentation in release 0.0.37**

The data-model, as represented in the database tables can
be used by the various strategies, as well as for analysis
and back-testing.

This section describes the database schema and usage patterns.

ticker_data
***********

The ticker_data table keeps basic data on traded stocks
which include the symbol name, company name & description
as well as industry & sector and similar symbols.

It is recommended to use the *market_miner* application
to periodically refresh the data.

The industry & sector data is informative for creating
a per sector / industry trend.