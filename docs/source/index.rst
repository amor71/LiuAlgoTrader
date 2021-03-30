A scalable algorithmic trading framework
========================================

Overview
^^^^^^^^

**LiuAlgoTrader** is a scalable, multi-process framework
for effective algorithmic trading. The framework is
intended to simplify development, testing,
deployment, backtesting and evaluating algo trading strategies.

LiuAlgoTrader can run on a laptop and
*hedge-on-the-go*, or run on a multi-core hosted Linux server
and it will optimize for best performance for either. The framework runs on Linux, Mac OS or, Windows.

LiuAlgoTrader is made of the following components:

- **trader**: the main application for real-time trading,
- **backtester**: re-running past trading sessions, back-testing strategies,
- **market_miner**: application for collecting market data and run market off-hours calculations & strategies,

AND

- **streamlit apps** & **analysis notebooks**: collection of visual applications and notebooks for analysis of trading sessions, backtesting, as well as various tools for improving trading algos.

The rest of the documentation explains how to install,
setup, configure and run trading & analysis
sessions w/ LiuAlgoTrader.


.. toctree::
   :maxdepth: 2

   What's New
   Quickstart
   (Advanced) Setup
   Concepts
   Configuration
   Scanners
   Strategies
   Trading
   Backtesting 
   Off-market
   Analysis
   Examples
   How to Contribute


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
