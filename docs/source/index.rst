A scalable algorithmic trading framework build on top Alpaca Market's APIs
==========================================================================

Overview
^^^^^^^^

LiuAlgoTrader is a Pythonic all-batteries-included framework
for effective algorithmic trading. The framework is
intended to simplify development, testing,
deployment and evaluating algo trading strategies.
The framework implements a multi-process
Producer-Consumer architecture, where the producer
process constantly gets ticker updates,
in near-real-time fashion and communicates over queues
with several consumers' processes. A consumer process
run **strategies** to act upon the tickers' event.

LiuAlgoTrader will split tickers between several consumers,
depending on the available hardware, and post events
to a specific consumer queue. Each event has a
time-stamp and the consumer infrastructure will
disregard events that are over-due and ensuring
that strategies never act upon old data.

LiuAlgoTrader is made of the following components:

- **trader**: the main application for trading
- **backtester**: re-running past trading sessions
- **market_miner**: application for collecting segments data
- **analysis notebooks**: collection of notebooks for analysis of trading sessions, backtesting, as well as various tools for improving trading algos.

The rest of the documentation explains how to install,
setup, configure and run trading & analysis
sessions w/ LiuAlgoTrader.


.. toctree::
   :maxdepth: 2

   WIP
   Quickstart
   Installation & Setup
   Configuration
   Scanners
   Strategies
   Analysis
   Back-testing
   How to Contribute


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
