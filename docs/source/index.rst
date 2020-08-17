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

.. toctree::
   :maxdepth: 2

   WIP
   Quickstart
   Analysis
   Back-testing
   How to Contribute


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
